from datetime import datetime
import string
import random
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm.attributes import flag_modified
from forms import UserForm, LoginForm, ParcelForm, EditUserForm, AdminRegistrationForm
from models import db, User, Parcel
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def generate_tracking_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def init_routes(app):
    from app import socketio, mail
    from flask_mail import Message

    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def index():
        form = ParcelForm()
        estimate = None
        parcels = Parcel.query.filter_by(user_id=current_user.id).all()
        logger.debug(f"Form submitted: {request.method}, Data: {request.form}")
        if request.method == 'POST':
            logger.debug(f"Form validation: {form.validate_on_submit()}")
            if form.validate_on_submit():
                distance_str = request.form.get('distance', '0')
                logger.debug(f"Distance received: {distance_str}")
                try:
                    distance = float(distance_str) if distance_str else 0.0
                except ValueError:
                    distance = 0.0
                    flash('Invalid distance value. Defaulting to 0.', 'warning')
                if 'estimate' in request.form:
                    weight = form.weight.data
                    cost = round(distance * weight * 0.5)
                    estimate = {'distance': distance, 'weight': weight, 'cost': cost}
                    logger.debug(f"Estimate calculated: {estimate}")
                else:
                    parcel = Parcel(
                        pickup=form.pickup_location.data,
                        destination=form.destination.data,
                        weight=form.weight.data,
                        distance=distance,
                        cost=round(distance * form.weight.data * 0.5),
                        user_id=current_user.id,
                        tracking_number=generate_tracking_number(),
                        status='Pending',  # Set initial status
                        tracking_history=[{  # Initialize tracking history
                            'timestamp': datetime.utcnow().isoformat(),
                            'status': 'Pending',
                            'location': form.pickup_location.data or 'N/A'
                        }]
                    )
                    db.session.add(parcel)
                    db.session.commit()
                    parcel = Parcel.query.get(parcel.id)
                    logger.debug(f"Parcel created: {parcel.tracking_number}, Tracking History: {parcel.tracking_history}")
                    logger.debug(f"Parcel created: {parcel.tracking_number}")

                    msg = Message('Parcel Created',
                                  sender=app.config['MAIL_USERNAME'],
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
                                                   '%Y-%m-%d %H:%M:%S'))
                    try:
                        mail.send(msg)
                        logger.debug(f"Creation email sent for parcel: {parcel.tracking_number}")
                    except Exception as e:
                        flash(f'Failed to send email notification: {str(e)}', 'danger')
                        logger.error(f"Email sending failed: {str(e)}")

                    return redirect(url_for('index'))
            else:
                logger.debug(f"Form errors: {form.errors}")
                flash('Invalid form data. Please check your inputs.', 'danger')
        return render_template('index.html', form=form, parcels=parcels, estimate=estimate,
                              google_maps_api_key=app.config['GOOGLE_MAPS_API_KEY'])

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        form = UserForm()
        if form.validate_on_submit():
            username = form.username.data
            email = form.email.data
            password = form.password.data
            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'danger')
                return redirect(url_for('register'))
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', form=form)

    @app.route('/admin/register', methods=['GET', 'POST'])
    @login_required
    def admin_register():
        if not current_user.is_admin:
            flash('Access denied: Admins only.', 'danger')
            return redirect(url_for('index'))
        form = AdminRegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered.', 'danger')
                return redirect(url_for('admin_register'))
            user = User(
                username=form.username.data,
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
                is_admin=True
            )
            db.session.add(user)
            db.session.commit()
            flash('Admin registered successfully.', 'success')
            return redirect(url_for('admin'))
        return render_template('admin_register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                flash('Login successful.', 'success')
                return redirect(url_for('index'))
            flash('Invalid email or password.', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out successfully.', 'success')
        return redirect(url_for('login'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        edit_form = EditUserForm(original_email=current_user.email)
        if edit_form.validate_on_submit():
            if User.query.filter_by(email=edit_form.email.data).first() and edit_form.email.data != current_user.email:
                flash('Email already in use.', 'danger')
                return redirect(url_for('profile'))
            current_user.username = edit_form.username.data
            current_user.email = edit_form.email.data
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('profile'))
        parcels = Parcel.query.filter_by(user_id=current_user.id).all()
        delivered = len([p for p in parcels if p.status == 'Delivered'])
        in_transit = len([p for p in parcels if p.status == 'In Transit'])
        return render_template('profile.html', edit_form=edit_form, parcels=parcels,
                              delivered=delivered, in_transit=in_transit)

    @app.route('/admin', methods=['GET', 'POST'])
    @login_required
    def admin():
        if not current_user.is_admin:
            flash('Access denied: Admins only.', 'danger')
            return redirect(url_for('index'))

        parcels = Parcel.query.all()

        if request.method == 'POST':
            logger.debug(f"Admin form data: {request.form}")

            for parcel in parcels:
                status = request.form.get(f'status_{parcel.id}')
                location = request.form.get(f'location_{parcel.id}')

                logger.debug(f"Processing parcel {parcel.tracking_number}: status={status}, location={location}")

                if status in ['Pending', 'In Transit', 'Delivered', 'Cancelled']:
                    # Keep current location if blank
                    updated_location = location.strip() if location and location.strip() else parcel.current_location

                    # Append to history only if status changes
                    if parcel.status != status:
                        new_entry = {
                            'timestamp': datetime.utcnow().isoformat(),
                            'status': status,
                            'location': updated_location or 'N/A'
                        }
                        parcel.tracking_history.append(new_entry)

                        # Mark the JSON column as modified so SQLAlchemy will persist it
                        flag_modified(parcel, "tracking_history")

                        # Update parcel
                        parcel.status = status
                        parcel.current_location = updated_location

                        logger.debug(f"Appended to {parcel.tracking_number} tracking history: {new_entry}")

                        # Notify via socket
                        socketio.emit('parcel_update', {
                            'tracking_number': parcel.tracking_number,
                            'status': status,
                            'location': updated_location
                        })

                        msg = Message('Parcel Status Update',
                                      sender=app.config['MAIL_USERNAME'],
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
                                                   timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
                        try:
                            mail.send(msg)
                            logger.debug(f"Update email sent for parcel: {parcel.tracking_number}")
                        except Exception as e:
                            flash(f'Failed to send email notification: {str(e)}', 'danger')
                            logger.error(f"Email sending failed: {str(e)}")

            db.session.commit()

            # Refresh for debugging/logging
            for parcel in parcels:
                db.session.refresh(parcel)
                logger.debug(f"Updated parcel {parcel.tracking_number}, Status: {parcel.status}, "
                             f"Tracking History: {parcel.tracking_history}")

            flash('Parcels updated successfully.', 'success')
            return redirect(url_for('admin'))

        return render_template('admin.html', parcels=parcels)

    @app.route('/cancel/<int:parcel_id>', methods=['POST'])
    @login_required
    def cancel(parcel_id):
        parcel = Parcel.query.get_or_404(parcel_id)
        if parcel.user_id != current_user.id:
            flash('Unauthorized.', 'danger')
            return redirect(url_for('index'))
        parcel.status = 'Cancelled'
        parcel.tracking_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'Cancelled',
            'location': parcel.current_location or 'N/A'
        })
        socketio.emit('parcel_update', {
            'tracking_number': parcel.tracking_number,
            'status': 'Cancelled',
            'location': parcel.current_location
        })
        msg = Message('Parcel Cancelled',
                      sender=app.config['MAIL_USERNAME'],
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
                                   timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        try:
            mail.send(msg)
            logger.debug(f"Cancellation email sent for parcel: {parcel.tracking_number}")
        except Exception as e:
            flash(f'Failed to send email notification: {str(e)}', 'danger')
            logger.error(f"Email sending failed: {str(e)}")
        db.session.commit()
        flash('Parcel cancelled.', 'success')
        return redirect(url_for('index'))

    @app.route('/change_destination/<int:parcel_id>', methods=['POST'])
    @login_required
    def change_destination(parcel_id):
        parcel = Parcel.query.get_or_404(parcel_id)
        if parcel.user_id != current_user.id:
            flash('Unauthorized.', 'danger')
            return redirect(url_for('index'))
        new_destination = request.form.get('new_destination')
        if new_destination:
            parcel.destination = new_destination
            parcel.tracking_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'status': parcel.status,
                'location': parcel.current_location or 'N/A'
            })
            socketio.emit('parcel_update', {
                'tracking_number': parcel.tracking_number,
                'status': parcel.status,
                'location': parcel.current_location
            })
            msg = Message('Parcel Destination Updated',
                          sender=app.config['MAIL_USERNAME'],
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
                                       timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            try:
                mail.send(msg)
                logger.debug(f"Destination update email sent for parcel: {parcel.tracking_number}")
            except Exception as e:
                flash(f'Failed to send email notification: {str(e)}', 'danger')
                logger.error(f"Email sending failed: {str(e)}")
            db.session.commit()
            flash('Destination updated.', 'success')
        else:
            flash('New destination required.', 'danger')
        return redirect(url_for('index'))

    @app.route('/track', methods=['GET', 'POST'])
    def track():
        if request.method == 'POST':
            tracking_number = request.form.get('tracking_number')
            parcel = Parcel.query.filter_by(tracking_number=tracking_number).first()
            if parcel:
                db.session.refresh(parcel)
                logger.debug(f"Tracked parcel: {parcel.tracking_number}, Tracking History: {parcel.tracking_history}")
                return render_template('track.html', parcel=parcel)
            flash('Invalid tracking number.', 'danger')
        return render_template('track.html', parcel=None)

    @app.template_filter('datetimeformat')
    def datetimeformat(value, format="%Y-%m-%d %H:%M:%S"):
        if isinstance(value, datetime):
            return value.strftime(format)
        try:
            return datetime.fromisoformat(str(value)).strftime(format)
        except Exception:
            return value