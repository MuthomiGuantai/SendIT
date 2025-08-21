from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm.attributes import flag_modified
from forms import UserForm, LoginForm, ParcelForm, EditUserForm, AdminRegistrationForm
from flask_mail import Message
from datetime import datetime
import string
import random
import logging

bp = Blueprint('main', __name__)

def generate_tracking_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    User = current_app.user_model
    Parcel = current_app.parcel_model
    Payment = current_app.payment_model

    form = ParcelForm()
    estimate = None
    parcels = Parcel.query.filter_by(user_id=current_user.id).all()

    payment_statuses = {
        parcel.id: Payment.query.filter_by(parcel_id=parcel.id).first()
        for parcel in parcels
    }

    if request.method == 'POST':
        if form.validate_on_submit():
            distance_str = request.form.get('distance', '0')
            try:
                distance = float(distance_str) if distance_str else 0.0
            except ValueError:
                distance = 0.0
                flash('Invalid distance value. Defaulting to 0.', 'warning')

            if 'estimate' in request.form:
                weight = form.weight.data
                cost = round(distance * weight * 0.5)
                estimate = {'distance': distance, 'weight': weight, 'cost': cost}
            else:
                parcel = Parcel(
                    pickup=form.pickup_location.data,
                    destination=form.destination.data,
                    weight=form.weight.data,
                    distance=distance,
                    cost=round(distance * form.weight.data * 0.5),
                    user_id=current_user.id,
                    tracking_number=generate_tracking_number(),
                    status='Pending',
                    tracking_history=[{
                        'timestamp': datetime.utcnow().isoformat(),
                        'status': 'Pending',
                        'location': form.pickup_location.data or 'N/A'
                    }]
                )
                current_app.db.session.add(parcel)
                current_app.db.session.commit()

                msg = Message('Parcel Created',
                              sender=current_app.config['MAIL_USERNAME'],
                              recipients=[parcel.user.email])
                msg.html = render_template('notification.html',
                                           username=parcel.user.username,
                                           tracking_number=parcel.tracking_number,
                                           status=parcel.status,
                                           pickup=parcel.pickup,
                                           destination=parcel.destination,
                                           weight=parcel.weight,
                                           cost=parcel.cost,
                                           current_location=parcel.current_location,
                                           timestamp=datetime.fromisoformat(
                                               parcel.tracking_history[-1]['timestamp']).strftime(
                                               '%Y-%m-%d %H:%M:%S'),
                                           message_type='parcel_update')
                try:
                    current_app.extensions['mail'].send(msg)
                except Exception as e:
                    current_app.logger.error(f'Failed to send parcel creation email for parcel {parcel.id}: {str(e)}')
                    flash(f'Failed to send email notification: {str(e)}', 'danger')

                return redirect(url_for('pay', parcel_id=parcel.id))
        else:
            flash('Invalid form data. Please check your inputs.', 'danger')

    return render_template('index.html', form=form, parcels=parcels, estimate=estimate, payment_statuses=payment_statuses,
                           google_maps_api_key=current_app.config['GOOGLE_MAPS_API_KEY'])

@bp.route('/register', methods=['GET', 'POST'])
def register():
    User = current_app.user_model

    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('main.register'))

        user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
            created_at=datetime.utcnow()
        )
        current_app.db.session.add(user)
        current_app.db.session.commit()

        # Send plain text registration confirmation email
        msg = Message('Welcome to SendIT - Registration Confirmation',
                      sender=current_app.config['MAIL_USERNAME'],
                      recipients=[user.email])
        msg.body = f"""Welcome to SendIT, {user.username}!
Your registration is complete.
Log in here: {url_for('main.login', _external=True)}"""
        try:
            current_app.extensions['mail'].send(msg)
            flash('Registration successful! A confirmation email has been sent to your email address.', 'success')
        except Exception as e:
            current_app.logger.error(f'Failed to send registration email for {user.email}: {str(e)}')
            flash(f'Registration successful, but failed to send confirmation email: {str(e)}', 'warning')

        return redirect(url_for('main.login'))

    return render_template('register.html', form=form)

@bp.route('/admin/register', methods=['GET', 'POST'])
@login_required
def admin_register():
    User = current_app.user_model

    if not current_user.is_admin:
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('main.index'))

    form = AdminRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('main.admin_register'))

        user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
            is_admin=True,
            created_at=datetime.utcnow()
        )
        current_app.db.session.add(user)
        current_app.db.session.commit()

        # Send plain text admin registration confirmation email
        msg = Message('Welcome to SendIT - Admin Registration Confirmation',
                      sender=current_app.config['MAIL_USERNAME'],
                      recipients=[user.email])
        msg.body = f"""Welcome to SendIT, {user.username}!
Your admin registration is complete.
Log in here: {url_for('main.login', _external=True)}"""
        try:
            current_app.extensions['mail'].send(msg)
            flash('Admin registered successfully! A confirmation email has been sent to their email address.', 'success')
        except Exception as e:
            current_app.logger.error(f'Failed to send admin registration email for {user.email}: {str(e)}')
            flash(f'Admin registered successfully, but failed to send confirmation email: {str(e)}', 'warning')

        return redirect(url_for('main.admin'))

    return render_template('admin_register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    User = current_app.user_model

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful.', 'success')
            next_page = request.args.get('next', url_for('main.index'))
            return redirect(next_page)
        flash('Invalid email or password.', 'danger')

    return render_template('login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.login'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    User = current_app.user_model
    Parcel = current_app.parcel_model
    Payment = current_app.payment_model

    edit_form = EditUserForm(original_email=current_user.email)
    if edit_form.validate_on_submit():
        if edit_form.email.data != current_user.email and User.query.filter_by(email=edit_form.email.data).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('main.profile'))

        current_user.username = edit_form.username.data
        current_user.email = edit_form.email.data
        current_app.db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.profile'))

    parcels = Parcel.query.filter_by(user_id=current_user.id).order_by(Parcel.created_at.desc()).limit(5).all()
    payment_statuses = {
        parcel.id: Payment.query.filter_by(parcel_id=parcel.id).first()
        for parcel in parcels
    }
    delivered = len([p for p in parcels if p.status == 'Delivered'])
    in_transit = len([p for p in parcels if p.status == 'In Transit'])

    total_spent = current_app.db.session.query(current_app.db.func.sum(Parcel.cost))\
        .filter_by(user_id=current_user.id, status='Delivered')\
        .scalar() or 0

    notifications = []
    for parcel in parcels:
        payment = payment_statuses.get(parcel.id)
        if parcel.status == 'Pending' and (not payment or payment.status != 'completed'):
            notifications.append({
                'message': f'Payment pending for parcel #{parcel.id} (Tracking: {parcel.tracking_number})',
                'timestamp': datetime.utcnow()
            })
        if parcel.status == 'In Transit':
            notifications.append({
                'message': f'Parcel #{parcel.id} is in transit to {parcel.destination}',
                'timestamp': parcel.tracking_history[-1]['timestamp']
            })
    if (datetime.utcnow() - current_user.created_at).days < 1:
        notifications.append({
            'message': 'Check your email for OTP verification if recently registered',
            'timestamp': current_user.created_at
        })

    return render_template('profile.html', edit_form=edit_form, parcels=parcels, payment_statuses=payment_statuses,
                           delivered=delivered, in_transit=in_transit, total_spent=total_spent, notifications=notifications)

@bp.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    Parcel = current_app.parcel_model

    if not current_user.is_admin:
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('main.index'))

    parcels = Parcel.query.all()

    if request.method == 'POST':
        for parcel in parcels:
            status = request.form.get(f'status_{parcel.id}')
            location = request.form.get(f'location_{parcel.id}')

            if status in ['Pending', 'In Transit', 'Delivered', 'Cancelled']:
                updated_location = location.strip() if location and location.strip() else parcel.current_location
                if parcel.status != status:
                    new_entry = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'status': status,
                        'location': updated_location or 'N/A'
                    }
                    parcel.tracking_history.append(new_entry)
                    flag_modified(parcel, "tracking_history")
                    parcel.status = status
                    parcel.current_location = updated_location

                    msg = Message('Parcel Status Update',
                                  sender=current_app.config['MAIL_USERNAME'],
                                  recipients=[parcel.user.email])
                    msg.html = render_template('notification.html',
                                               username=parcel.user.username,
                                               tracking_number=parcel.tracking_number,
                                               status=status,
                                               pickup=parcel.pickup,
                                               destination=parcel.destination,
                                               weight=parcel.weight,
                                               cost=parcel.cost,
                                               current_location=updated_location or 'N/A',
                                               timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                                               message_type='parcel_update')
                    try:
                        current_app.extensions['mail'].send(msg)
                    except Exception as e:
                        current_app.logger.error(f'Failed to send parcel update email for parcel {parcel.id}: {str(e)}')
                        flash(f'Failed to send email notification: {str(e)}', 'danger')

        current_app.db.session.commit()
        flash('Parcels updated successfully.', 'success')
        return redirect(url_for('main.admin'))

    return render_template('admin.html', parcels=parcels)

@bp.route('/cancel/<int:parcel_id>', methods=['POST'])
@login_required
def cancel(parcel_id):
    Parcel = current_app.parcel_model

    parcel = Parcel.query.get_or_404(parcel_id)
    if parcel.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('main.index'))

    parcel.status = 'Cancelled'
    parcel.tracking_history.append({
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'Cancelled',
        'location': parcel.current_location or 'N/A'
    })

    msg = Message('Parcel Cancelled',
                  sender=current_app.config['MAIL_USERNAME'],
                  recipients=[parcel.user.email])
    msg.html = render_template('notification.html',
                               username=parcel.user.username,
                               tracking_number=parcel.tracking_number,
                               status='Cancelled',
                               pickup=parcel.pickup,
                               destination=parcel.destination,
                               weight=parcel.weight,
                               cost=parcel.cost,
                               current_location=parcel.current_location or 'N/A',
                               timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                               message_type='parcel_update')
    try:
        current_app.extensions['mail'].send(msg)
    except Exception as e:
        current_app.logger.error(f'Failed to send parcel cancellation email for parcel {parcel.id}: {str(e)}')
        flash(f'Failed to send email notification: {str(e)}', 'danger')

    current_app.db.session.commit()
    flash('Parcel cancelled.', 'success')
    return redirect(url_for('main.index'))

@bp.route('/change_destination/<int:parcel_id>', methods=['POST'])
@login_required
def change_destination(parcel_id):
    Parcel = current_app.parcel_model

    parcel = Parcel.query.get_or_404(parcel_id)
    if parcel.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('main.index'))

    new_destination = request.form.get('new_destination')
    if new_destination:
        parcel.destination = new_destination
        parcel.tracking_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'status': parcel.status,
            'location': parcel.current_location or 'N/A'
        })

        msg = Message('Parcel Destination Updated',
                      sender=current_app.config['MAIL_USERNAME'],
                      recipients=[parcel.user.email])
        msg.html = render_template('notification.html',
                                   username=parcel.user.username,
                                   tracking_number=parcel.tracking_number,
                                   status=parcel.status,
                                   pickup=parcel.pickup,
                                   destination=new_destination,
                                   weight=parcel.weight,
                                   cost=parcel.cost,
                                   current_location=parcel.current_location or 'N/A',
                                   timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                                   message_type='parcel_update')
        try:
            current_app.extensions['mail'].send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send destination update email for parcel {parcel.id}: {str(e)}')
            flash(f'Failed to send email notification: {str(e)}', 'danger')

        current_app.db.session.commit()
        flash('Destination updated.', 'success')
    else:
        flash('New destination required.', 'danger')

    return redirect(url_for('main.index'))

@bp.route('/track', methods=['GET', 'POST'])
def track():
    Parcel = current_app.parcel_model

    if request.method == 'POST':
        tracking_number = request.form.get('tracking_number')
        parcel = Parcel.query.filter_by(tracking_number=tracking_number).first()
        if parcel:
            return render_template('track.html', parcel=parcel)
        flash('Invalid tracking number.', 'danger')

    return render_template('track.html', parcel=None)