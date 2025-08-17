from flask import Flask, request, redirect, url_for, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from dotenv import load_dotenv
from datetime import datetime
import os
import sys
import base64
import requests
import logging

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
socketio = SocketIO()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    load_dotenv()

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(24)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sendit.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
    app.config['GOOGLE_MAPS_API_KEY'] = os.getenv('GOOGLE_MAPS_API_KEY')

    # Initialize extensions with app
    db.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Import models
    from models import init_models
    User, Parcel, Payment = init_models(db)

    # Store models and db in app context
    app.user_model = User
    app.parcel_model = Parcel
    app.payment_model = Payment
    app.db = db

    # Create tables
    with app.app_context():
        db.create_all()

    # User loader
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Template filter
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format="%Y-%m-%d %H:%M:%S"):
        if isinstance(value, datetime):
            return value.strftime(format)
        try:
            return datetime.fromisoformat(str(value)).strftime(format)
        except Exception:
            return value

    # M-Pesa functions
    def get_mpesa_access_token():
        consumer_key = os.environ.get('MPESA_CONSUMER_KEY')
        consumer_secret = os.environ.get('MPESA_CONSUMER_SECRET')
        api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials' if os.environ.get(
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

    def initiate_stk_push(phone_number, amount, parcel_id):
        access_token = get_mpesa_access_token()
        if not access_token:
            return None, "Failed to obtain access token"

        api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest' if os.environ.get(
            'MPESA_ENV') == 'sandbox' else 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        shortcode = os.environ.get('MPESA_SHORTCODE')
        passkey = os.environ.get('MPESA_PASSKEY')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
        callback_url = os.environ.get('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok.io/mpesa_callback')

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

    # M-Pesa routes
    @app.route('/pay/<int:parcel_id>', methods=['GET', 'POST'])
    @login_required
    def pay(parcel_id):
        from forms import PaymentForm
        parcel = Parcel.query.get_or_404(parcel_id)
        if parcel.user_id != current_user.id:
            flash('Unauthorized access.', 'danger')
            return redirect(url_for('main.index'))

        form = PaymentForm()
        if form.validate_on_submit():
            phone_number = form.phone_number.data
            payment = Payment(
                parcel_id=parcel_id,
                user_id=current_user.id,
                amount=parcel.cost,
                phone_number=phone_number,
                status='pending'
            )
            db.session.add(payment)
            db.session.commit()

            response, error = initiate_stk_push(phone_number, parcel.cost, parcel_id)
            if error:
                payment.status = 'failed'
                db.session.commit()
                flash(f'Payment initiation failed: {error}', 'danger')
                return redirect(url_for('main.index'))

            payment.transaction_id = response.get('CheckoutRequestID')
            db.session.commit()
            flash('Payment request sent to your phone. Please complete the M-Pesa STK Push.', 'success')
            return redirect(url_for('main.index'))

        return render_template('pay.html', parcel=parcel, form=form)

    @app.route('/mpesa_callback', methods=['POST'])
    def mpesa_callback():
        data = request.get_json()
        app.logger.debug(f"M-Pesa callback received: {data}")
        if not data:
            app.logger.error("No data received in callback")
            return {"ResultCode": 1, "ResultDesc": "No data received"}, 400

        result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')

        if not checkout_request_id:
            app.logger.error("No CheckoutRequestID in callback")
            return {"ResultCode": 1, "ResultDesc": "Invalid callback data"}, 400

        payment = Payment.query.filter_by(transaction_id=checkout_request_id).first()
        if not payment:
            app.logger.error(f"No payment found for CheckoutRequestID: {checkout_request_id}")
            return {"ResultCode": 1, "ResultDesc": "Payment not found"}, 404

        if result_code == 0:
            payment.status = 'completed'
            parcel = Parcel.query.get(payment.parcel_id)
            parcel.status = 'In Transit'
            parcel.tracking_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'In Transit',
                'location': parcel.current_location or 'N/A'
            })
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(parcel, "tracking_history")
            app.logger.debug(f"Payment completed for parcel: {parcel.tracking_number}")
            user = User.query.get(payment.user_id)
            msg = Message(
                subject='SendIT Payment Confirmation',
                sender=app.config['MAIL_USERNAME'],
                recipients=[user.email],
                html=render_template('notification.html',
                                     username=user.username,
                                     tracking_number=parcel.tracking_number,
                                     status='In Transit',
                                     pickup=parcel.pickup,
                                     destination=parcel.destination,
                                     weight=parcel.weight,
                                     cost=parcel.cost,
                                     current_location=parcel.current_location or 'N/A',
                                     payment_status='Completed',
                                     timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            )
            try:
                mail.send(msg)
                app.logger.debug(f"Payment confirmation email sent to {user.email}")
            except Exception as e:
                app.logger.error(f"Failed to send payment confirmation email to {user.email}: {e}")
        else:
            payment.status = 'failed'
            app.logger.debug(f"Payment failed for CheckoutRequestID: {checkout_request_id}")
            user = User.query.get(payment.user_id)
            msg = Message(
                subject='SendIT Payment Failed',
                sender=app.config['MAIL_USERNAME'],
                recipients=[user.email],
                html=render_template('notification.html',
                                     username=user.username,
                                     tracking_number=Parcel.query.get(payment.parcel_id).tracking_number,
                                     status=Parcel.query.get(payment.parcel_id).status,
                                     pickup=Parcel.query.get(payment.parcel_id).pickup,
                                     destination=Parcel.query.get(payment.parcel_id).destination,
                                     weight=Parcel.query.get(payment.parcel_id).weight,
                                     cost=Parcel.query.get(payment.parcel_id).cost,
                                     current_location=Parcel.query.get(payment.parcel_id).current_location or 'N/A',
                                     payment_status='Failed',
                                     timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            )
            try:
                mail.send(msg)
                app.logger.debug(f"Payment failure email sent to {user.email}")
            except Exception as e:
                app.logger.error(f"Failed to send payment failure email to {user.email}: {e}")
                flash(f'Failed to send payment failure email: {str(e)}', 'danger')

        db.session.commit()
        return {"ResultCode": 0, "ResultDesc": "Callback processed"}, 200

    return app

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)