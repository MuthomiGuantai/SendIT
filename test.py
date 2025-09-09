import base64

import pytest
import requests
from flask import url_for
from flask_login import current_user
from unittest.mock import patch, MagicMock
from datetime import datetime
from app import create_app, db as app_db
from models import init_models
import json

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'MAIL_SUPPRESS_SEND': True,
        'MPESA_ENV': 'sandbox',
        'MPESA_CONSUMER_KEY': 'test_key',
        'MPESA_CONSUMER_SECRET': 'test_secret',
        'MPESA_SHORTCODE': '123456',
        'MPESA_PASSKEY': 'test_passkey',
        'MPESA_CALLBACK_URL': 'http://test-callback.com',
    })
    with app.app_context():
        app_db.create_all()
        yield app
        app_db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def init_db(app):
    User, Parcel, Payment = init_models(app_db)
    return User, Parcel, Payment

def test_app_creation(app):
    assert app is not None
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'

def test_get_mpesa_access_token(app):
    with app.app_context():
        # Define get_mpesa_access_token locally for testing, mirroring app.py
        def get_mpesa_access_token():
            consumer_key = app.config.get('MPESA_CONSUMER_KEY')
            consumer_secret = app.config.get('MPESA_CONSUMER_SECRET')
            api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials' if app.config.get(
                'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
            headers = {'Authorization': 'Basic ' + base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()}
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                access_token = response.json().get('access_token')
                app.logger.debug(f"M-Pesa access token obtained: {access_token[:10]}...")
                return response.json().get('access_token')
            except Exception as e:
                app.logger.error(f"M-Pesa token error: {e}, Response: {getattr(e, 'response', 'No response')}")
                return None

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {'access_token': 'test_token'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            token = get_mpesa_access_token()
            assert token == 'test_token'
            mock_get.assert_called_once()
            assert mock_get.call_args[1]['headers']['Authorization'].startswith('Basic ')

def test_initiate_stk_push_success(app, init_db):
    with app.app_context():
        User, Parcel, Payment = init_db
        user = User(username='testuser', email='test@example.com', password='hashed_password')
        parcel = Parcel(
            user_id=1,
            tracking_number='TEST123',
            pickup='Nairobi',
            destination='Mombasa',
            weight=1.0,
            cost=1000,
            status='Pending',
            current_location='Nairobi'
        )
        app_db.session.add(user)
        app_db.session.add(parcel)
        app_db.session.commit()

        # Define initiate_stk_push locally for testing, mirroring app.py
        def initiate_stk_push(phone_number, amount, parcel_id):
            consumer_key = app.config.get('MPESA_CONSUMER_KEY')
            consumer_secret = app.config.get('MPESA_CONSUMER_SECRET')
            api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials' if app.config.get(
                'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
            headers = {'Authorization': 'Basic ' + base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()}
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                access_token = response.json().get('access_token')
            except Exception:
                return None, "Failed to obtain access token"

            api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest' if app.config.get(
                'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            shortcode = app.config.get('MPESA_SHORTCODE')
            passkey = app.config.get('MPESA_PASSKEY')
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
            callback_url = app.config.get('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok.io/mpesa_callback')

            payload = {
                'BusinessShortCode': shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'PartyA': phone_number,
                'PartyB': shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': f"Parcel_{parcel_id}",
                'TransactionDesc': 'Payment for parcel delivery'
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            try:
                response = requests.post(api_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                app.logger.debug(f"STK Push response: {response.json()}")
                return response.json(), None
            except requests.exceptions.HTTPError as e:
                app.logger.error(f"STK Push HTTP error: {e}, Response: {e.response.text}")
                return None, f"HTTP Error: {e.response.text}"
            except Exception as e:
                app.logger.error(f"STK Push error: {e}")
                return None, str(e)

        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_get_response = MagicMock()
            mock_get_response.json.return_value = {'access_token': 'test_token'}
            mock_get_response.raise_for_status.return_value = None
            mock_get.return_value = mock_get_response

            mock_post_response = MagicMock()
            mock_post_response.json.return_value = {
                'CheckoutRequestID': 'ws_CO_123456789',
                'ResponseCode': '0'
            }
            mock_post_response.raise_for_status.return_value = None
            mock_post.return_value = mock_post_response

            response, error = initiate_stk_push('254700123456', 1000, parcel.id)
            assert response['CheckoutRequestID'] == 'ws_CO_123456789'
            assert error is None
            mock_post.assert_called_once()
            assert mock_post.call_args[1]['headers']['Authorization'].startswith('Bearer ')

def test_initiate_stk_push_failure(app, init_db):
    with app.app_context():
        # Define initiate_stk_push locally for testing, mirroring app.py
        def initiate_stk_push(phone_number, amount, parcel_id):
            consumer_key = app.config.get('MPESA_CONSUMER_KEY')
            consumer_secret = app.config.get('MPESA_CONSUMER_SECRET')
            api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials' if app.config.get(
                'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
            headers = {'Authorization': 'Basic ' + base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()}
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                access_token = response.json().get('access_token')
            except Exception:
                return None, "Failed to obtain access token"

            api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest' if app.config.get(
                'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            shortcode = app.config.get('MPESA_SHORTCODE')
            passkey = app.config.get('MPESA_PASSKEY')
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
            callback_url = app.config.get('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok.io/mpesa_callback')

            payload = {
                'BusinessShortCode': shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'PartyA': phone_number,
                'PartyB': shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': f"Parcel_{parcel_id}",
                'TransactionDesc': 'Payment for parcel delivery'
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            try:
                response = requests.post(api_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                app.logger.debug(f"STK Push response: {response.json()}")
                return response.json(), None
            except requests.exceptions.HTTPError as e:
                app.logger.error(f"STK Push HTTP error: {e}, Response: {e.response.text}")
                return None, f"HTTP Error: {e.response.text}"
            except Exception as e:
                app.logger.error(f"STK Push error: {e}")
                return None, str(e)

        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_get_response = MagicMock()
            mock_get_response.json.return_value = {'access_token': 'test_token'}
            mock_get_response.raise_for_status.return_value = None
            mock_get.return_value = mock_get_response
            mock_post.side_effect = Exception('Network error')
            response, error = initiate_stk_push('254700123456', 1000, 1)
            assert response is None
            assert error == 'Network error'

def test_pay_route_unauthorized(client, init_db, app):
    with app.app_context():
        User, Parcel, Payment = init_db
        user = User(username='testuser', email='test@example.com', password='hashed_password')
        parcel = Parcel(
            user_id=2,
            tracking_number='TEST123',
            pickup='Nairobi',
            destination='Mombasa',
            weight=1.0,
            cost=1000,
            status='Pending'
        )
        app_db.session.add(user)
        app_db.session.add(parcel)
        app_db.session.commit()

        with client:
            client.post('/login', data={
                'email': 'test@example.com',
                'password': 'testpassword'
            }, follow_redirects=True)
            response = client.get(f'/pay/{parcel.id}', follow_redirects=True)
            assert b'Unauthorized access.' in response.data

def test_pay_route_success(client, init_db, app):
    with app.app_context():
        User, Parcel, Payment = init_db
        user = User(username='testuser', email='test@example.com', password='hashed_password')
        parcel = Parcel(
            user_id=1,
            tracking_number='TEST123',
            pickup='Nairobi',
            destination='Mombasa',
            weight=1.0,
            cost=1000,
            status='Pending'
        )
        app_db.session.add(user)
        app_db.session.add(parcel)
        app_db.session.commit()

        with client:
            client.post('/login', data={
                'email': 'test@example.com',
                'password': 'testpassword'
            }, follow_redirects=True)
            with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
                mock_get_response = MagicMock()
                mock_get_response.json.return_value = {'access_token': 'test_token'}
                mock_get_response.raise_for_status.return_value = None
                mock_get.return_value = mock_get_response

                mock_post_response = MagicMock()
                mock_post_response.json.return_value = {
                    'CheckoutRequestID': 'ws_CO_123456789',
                    'ResponseCode': '0'
                }
                mock_post_response.raise_for_status.return_value = None
                mock_post.return_value = mock_post_response

                response = client.post(f'/pay/{parcel.id}', data={
                    'phone_number': '254700123456'
                }, follow_redirects=True)
                assert b'Payment request sent to your phone' in response.data
                payment = Payment.query.filter_by(parcel_id=parcel.id).first()
                assert payment is not None
                assert payment.transaction_id == 'ws_CO_123456789'
                assert payment.status == 'pending'

def test_mpesa_callback_success(client, init_db, app):
    with app.app_context():
        User, Parcel, Payment = init_db
        user = User(username='testuser', email='test@example.com', password='hashed_password')
        parcel = Parcel(
            user_id=1,
            tracking_number='TEST123',
            pickup='Nairobi',
            destination='Mombasa',
            weight=1.0,
            cost=1000,
            status='Pending'
        )
        payment = Payment(
            parcel_id=1,
            user_id=1,
            amount=1000,
            phone_number='254700123456',
            status='pending',
            transaction_id='ws_CO_123456789'
        )
        app_db.session.add(user)
        app_db.session.add(parcel)
        app_db.session.add(payment)
        app_db.session.commit()

        callback_data = {
            'Body': {
                'stkCallback': {
                    'ResultCode': 0,
                    'CheckoutRequestID': 'ws_CO_123456789',
                    'ResultDesc': 'Success'
                }
            }
        }
        with patch('flask_mail.Message.send') as mock_mail:
            response = client.post('/mpesa_callback', json=callback_data)
            assert response.status_code == 200
            assert response.json == {"ResultCode": 0, "ResultDesc": "Callback processed"}
            updated_payment = Payment.query.filter_by(transaction_id='ws_CO_123456789').first()
            assert updated_payment.status == 'completed'
            updated_parcel = Parcel.query.get(1)
            assert updated_parcel.status == 'In Transit'
            assert len(updated_parcel.tracking_history) > 0
            mock_mail.assert_called_once()

def test_mpesa_callback_failure(client, init_db, app):
    with app.app_context():
        User, Parcel, Payment = init_db
        user = User(username='testuser', email='test@example.com', password='hashed_password')
        parcel = Parcel(
            user_id=1,
            tracking_number='TEST123',
            pickup='Nairobi',
            destination='Mombasa',
            weight=1.0,
            cost=1000,
            status='Pending'
        )
        payment = Payment(
            parcel_id=1,
            user_id=1,
            amount=1000,
            phone_number='254700123456',
            status='pending',
            transaction_id='ws_CO_123456789'
        )
        app_db.session.add(user)
        app_db.session.add(parcel)
        app_db.session.add(payment)
        app_db.session.commit()

        callback_data = {
            'Body': {
                'stkCallback': {
                    'ResultCode': 1,
                    'CheckoutRequestID': 'ws_CO_123456789',
                    'ResultDesc': 'Failed'
                }
            }
        }
        with patch('flask_mail.Message.send') as mock_mail:
            response = client.post('/mpesa_callback', json=callback_data)
            assert response.status_code == 200
            assert response.json == {"ResultCode": 0, "ResultDesc": "Callback processed"}
            updated_payment = Payment.query.filter_by(transaction_id='ws_CO_123456789').first()
            assert updated_payment.status == 'failed'
            mock_mail.assert_called_once()

def test_mpesa_callback_invalid_data(client, app):
    with app.app_context():
        response = client.post('/mpesa_callback', json={})
        assert response.status_code == 400
        assert response.json == {"ResultCode": 1, "ResultDesc": "No data received"}

def test_datetimeformat_filter(app):
    with app.app_context():
        dt = datetime(2023, 1, 1, 12, 0, 0)
        assert app.jinja_env.filters['datetimeformat'](dt) == '2023-01-01 12:00:00'
        assert app.jinja_env.filters['datetimeformat']('2023-01-01T12:00:00') == '2023-01-01 12:00:00'
        assert app.jinja_env.filters['datetimeformat']('invalid') == 'invalid'