from flask import render_template, request, redirect, url_for, flash
from forms import UserForm, LoginForm, ParcelForm, EditUserForm, AdminRegistrationForm
from models import db, User, Parcel
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

def init_routes(app):
    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def index():
        form = ParcelForm()
        parcels = Parcel.query.filter_by(user_id=current_user.id).all()
        if form.validate_on_submit():
            pickup = form.pickup_location.data
            destination = form.destination.data
            weight = form.weight.data
            distance = float(request.form.get('distance', 0))
            cost = round(distance * weight * 0.5)  # Round to whole number
            parcel = Parcel(
                pickup=pickup,
                destination=destination,
                weight=weight,
                distance=distance,
                cost=cost,
                user_id=current_user.id
            )
            db.session.add(parcel)
            db.session.commit()
            flash('Parcel created!', 'success')
            return redirect(url_for('index'))
        return render_template('index.html', form=form, parcels=parcels,
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
                password=generate_password_hash(form.password.data),
                is_admin=True  # Set admin role for admin registration
            )
            db.session.add(user)
            db.session.commit()
            flash('Admin registration successful!', 'success')
            return redirect(url_for('admin'))
        return render_template('admin_register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        print(f"Request: {request.method}, Form data: {request.form}")  # Debug
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            print(f"Login attempt - Email: {email}, Password: {bool(password)}")  # Debug
            user = User.query.filter_by(email=email).first()
            print(f"User: {user}, Email: {email}")  # Debug
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True)
                print(f"Login success: {user.email}")  # Debug
                flash('Logged in!', 'success')
                return redirect(request.args.get('next') or url_for('index'))
            else:
                print("Login failed: Invalid credentials")  # Debug
                flash('Invalid email or password.', 'danger')
        else:
            if request.method == 'POST':
                print(f"Validation failed: {form.errors}")  # Debug
                flash(f'Validation failed: {form.errors}', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out.', 'success')
        return redirect(url_for('login'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        edit_form = EditUserForm(original_email=current_user.email)
        parcels = Parcel.query.filter_by(user_id=current_user.id).all()
        delivered = sum(1 for p in parcels if p.status == 'Delivered')
        in_transit = sum(1 for p in parcels if p.status == 'In Transit')
        if edit_form.validate_on_submit():
            current_user.username = edit_form.username.data
            current_user.email = edit_form.email.data
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        elif request.method == 'POST':
            flash('Failed to update profile. Check your inputs.', 'danger')
        return render_template('profile.html', parcels=parcels, delivered=delivered, in_transit=in_transit, edit_form=edit_form)

    @app.route('/admin', methods=['GET', 'POST'])
    @login_required
    def admin():
        if not current_user.is_admin:
            flash('Access denied: Admins only.', 'danger')
            return redirect(url_for('index'))
        parcels = Parcel.query.all()
        if request.method == 'POST':
            for parcel in parcels:
                status = request.form.get(f'status_{parcel.id}')
                location = request.form.get(f'location_{parcel.id}')
                if status in ['Pending', 'In Transit', 'Delivered', 'Cancelled']:
                    parcel.status = status
                if location:
                    parcel.current_location = location
            db.session.commit()
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
            db.session.commit()
            flash('Destination updated.', 'success')
        else:
            flash('New destination required.', 'danger')
        return redirect(url_for('index'))