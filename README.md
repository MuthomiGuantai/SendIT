# SendIT - Parcel Delivery Application

![SendIT Logo](static/logo.svg)

SendIT is a Flask-based web application inspired by DHL and Sendy, designed for parcel delivery management. It allows users to create, track, and manage parcels with real-time updates, cost estimation, and email notifications. The application features a responsive UI with a purple/yellow color scheme (`#6b46c1`, `#805ad5`, `#b794f4`, `#f0f4ff`, `#FFC107`) and Inter/Montserrat fonts, ensuring a modern and user-friendly experience.

Deployed at: [https://sendit-74d3.onrender.com/](https://sendit-74d3.onrender.com/)

## Features

- **Parcel Creation**: Users can create parcels by specifying pickup, destination, and weight, with automatic cost estimation (distance × weight × 0.5 KES).
- **Real-Time Tracking**: Track parcels with live updates using SocketIO and visualize routes on a Google Maps interface.
- **Email Notifications**: Automated emails for parcel creation, status updates, and cancellations, styled with SendIT branding.
- **Cost Estimator**: Calculate delivery costs based on distance and weight.
- **User and Admin Roles**: Supports regular users and admins, with admin-only access to manage all parcels.
- **Responsive Design**: Mobile-friendly UI with a hamburger menu and theme toggle (light/dark modes).
- **Secure Authentication**: User registration and login with password hashing using Flask-Login.
- **Admin Dashboard**: Admins can update parcel statuses and view all parcels/users.
- **Theme Toggle**: Switch between light and dark themes, persisted via local storage.
- **Database**: SQLite (`sendit.db`) stores user and parcel data, including tracking history.
- **Payments**: MPESA (`stk-push`) sends and stk push notification for customers to pay for their parcel cost.

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-SocketIO, Flask-Mail
- **Frontend**: HTML, CSS (custom `style.css`), JavaScript, Google Maps API, SocketIO
- **Fonts**: Inter, Montserrat (via Google Fonts)
- **Database**: SQLite (`sendit.db`)
- **Deployment**: Render (https://sendit-74d3.onrender.com/)
- **Dependencies**: Python 3.13, Werkzeug, python-dotenv

## Installation

### Prerequisites

- Python 3.13
- pip
- SQLite
- Google Maps API Key
- Gmail account with App Password for email notifications

### Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/sendit.git
   cd sendit
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install flask flask-wtf python-dotenv flask-login flask-sqlalchemy flask-socketio flask-mail
   ```

4. **Configure Environment Variables**:
   - Create a `.env` file in the project root:
     ```
     SECRET_KEY=your_random_secret_key_here
     GOOGLE_MAPS_API_KEY=your_valid_google_maps_api_key_here
     MAIL_USERNAME=your_email@gmail.com
     MAIL_PASSWORD=your_app_password
     MPESA_CALLBACK_URL=your_valid_mpesa_callback_url
     MPESA_CONSUMER_KEY=your_valid_mpesa_consumer_key
     MPESA_CONSUMER_SECRET=your_valid_mpesa_consumer_secret
     MPESA_ENV=specify_your_mpesa_environment
     MPESA_PASSKEY=your_mpesa_passkey
     MPESA_SHORTCODE=a_valid_mpesa_shortcode
     ```
   - Obtain a Google Maps API Key from [Google Cloud Console](https://console.cloud.google.com/).
   - Generate a Gmail App Password at [Google Account Settings](https://myaccount.google.com/security).

5. **Initialize the Database**:
   - Run `app.py` to create `sendit.db`:
     ```bash
     python app.py
     ```
   - Verify tables:
     ```sql
     sqlite3 sendit.db
     .tables
     PRAGMA table_info(user);
     PRAGMA table_info(parcel);
     ```

6. **Run the Application**:
   ```bash
   python app.py
   ```
   - Access at `http://127.0.0.1:5000`.

### Project Structure

```
sendit/
├── static/
│   ├── style.css           # Custom CSS with purple/yellow theme
│   └── logo.svg           # SendIT logo
├── templates/
│   ├── email/
│   │   ├── notification.html  # HTML email template
│   │   └── notification.txt   # Plain-text email template
│   ├── base.html          # Base template with navbar and theme toggle
│   ├── index.html         # Home page with map and parcel creation
│   ├── track.html         # Parcel tracking page
│   ├── login.html         # Login page
│   ├── register.html      # Registration page
│   ├── admin.html         # Admin dashboard
│   ├── admin_register.html # Admin registration
│   └── profile.html       # User profile
├── app.py                 # Flask app configuration
├── routes.py              # Application routes
├── models.py              # SQLAlchemy models
├── forms.py               # WTForms for input validation
├── create_users.py        # Script to create users/admins
├── sendit.db              # SQLite database
└── .env                   # Environment variables
```

## Usage

1. **Register/Login**:
   - Register at `/register` or log in at `/login`.
   - Use `create_users.py` to create test users:
     ```bash
     python create_users.py
     ```
     - Default users: `testuser` (user@example.com, password123), `adminuser` (admin@example.com, adminpass123).

2. **Create a Parcel**:
   - At `/`, enter pickup, destination, and weight.
   - View estimated cost and submit to create a parcel (e.g., tracking number `OI2X16UW768D2F8Q`).
   - Receive an email notification with parcel details.

3. **Track a Parcel**:
   - Go to `/track`, enter the tracking number.
   - View real-time status and map visualization.

4. **Admin Functions**:
   - Log in as `adminuser` and access `/admin`.
   - Update parcel statuses (e.g., Pending → In Transit → Delivered).
   - Users receive email and SocketIO updates.

5. **Theme Toggle**:
   - Click the theme toggle button (🌙/☀️) in the navbar to switch between light/dark modes.

6. **Payment**:
   - Create a parcel you will be routed to `/pay` enter phone number and proceed.
   - An mpesa stk-push will pop up on your phone proceed to enter your mpesa pin and pay.
   - You can also pay from your list of parcels in `/`, for an unpaid parcel there should be a `Pay Now` link that routes you to `/pay`.

## Deployment

The application is deployed on Render at [https://sendit-74d3.onrender.com/](https://sendit-74d3.onrender.com/).

### Deploying to Render

1. **Push to GitHub**:
   - Ensure all files are committed, including `.env` (without sensitive data).
   - Create a repository and push:
     ```bash
     git push origin main
     ```

2. **Create a Render Web Service**:
   - Sign in to [Render](https://render.com).
   - Create a new Web Service, connect your GitHub repository.
   - Set:
     - **Runtime**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
   - Add environment variables in Render’s dashboard:
     ```
     SECRET_KEY
     GOOGLE_MAPS_API_KEY
     MAIL_USERNAME
     MAIL_PASSWORD
     MPESA_CALLBACK_URL
     MPESA_CONSUMER_KEY
     MPESA_CONSUMER_SECRET
     MPESA_ENV
     MPESA_PASSKEY
     MPESA_SHORTCODE
     ```

3. **Generate `requirements.txt`**:
   ```bash
   pip freeze > requirements.txt
   ```

4. **Deploy**:
   - Trigger a deployment in Render.
   - Verify at `https://sendit-74d3.onrender.com/`.

## Database Schema

- **User**:
  ```sql
  CREATE TABLE user (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      is_admin BOOLEAN NOT NULL DEFAULT 0
  );
  ```

- **Parcel**:
  ```sql
  CREATE TABLE parcel (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      pickup TEXT,
      destination TEXT,
      weight REAL,
      distance REAL,
      cost REAL,
      status TEXT,
      tracking_number TEXT UNIQUE,
      tracking_history TEXT,
      current_location TEXT
  );
  ```

## Testing

1. **Local Testing**:
   - Run `app.py` and access `http://127.0.0.1:5000`.
   - Test:
     - Login: `user@example.com` (password123), `admin@example.com` (adminpass123).
     - Parcel creation: Pickup “Nairobi, Kenya”, Destination “Mombasa, Kenya”, Weight 2.5 kg.
     - Tracking: Enter tracking number (e.g., `OI2X16UW768D2F8Q`).
     - Admin: Update parcel status at `/admin`.
     - Email: Check `user@example.com` for notifications.
     - Theme: Toggle light/dark modes.
     - Mobile: Use Chrome DevTools (iPhone SE ~375px) for responsiveness.

2. **Deployed Testing**:
   - Access `https://sendit-74d3.onrender.com/`.
   - Repeat local tests.
   - Verify map loads, SocketIO updates, and email delivery.

3. **Database Verification**:
   ```sql
   sqlite3 sendit.db
   SELECT id, username, email, is_admin FROM user;
   SELECT tracking_number, status, current_location, tracking_history FROM parcel;
   ```

## Debugging

- **Email Issues**:
  - Check `.env` for valid `MAIL_USERNAME` and `MAIL_PASSWORD`.
  - Verify Gmail App Password.
  - Check spam/junk folder.
  - Test Flask-Mail:
    ```python
    from flask_mail import Message
    with app.app_context():
        msg = Message("Test", recipients=["user@example.com"], body="Test email")
        app.mail.send(msg)
    ```

- **Map Issues**:
  - Ensure `GOOGLE_MAPS_API_KEY` is valid.
  - Check browser console (F12 > Console) for errors.
  - Verify `https://maps.googleapis.com/maps/api/js` loads.

- **SocketIO**:
  - Confirm `https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.1/socket.io.min.js` loads.
  - Check real-time updates on `/track`.

- **Database**:
  - Verify schema with `PRAGMA table_info(user);`.
  - Check for duplicate users/parcels:
    ```sql
    DELETE FROM user WHERE username IN ('testuser', 'adminuser');
    ```

## Future Enhancements

- **User Dashboard**: Display parcel stats (total sent, average cost) with Chart.js.
- **Driver Tracking**: Show live driver locations on the map for “In Transit” parcels.
- **Payment Integration**: Add M-Pesa for online payments.
- **Push Notifications**: Implement browser push notifications for status updates.
- **Multi-Language Support**: Add Swahili translations with Flask-Babel.
- **Parcel Rating**: Allow users to rate deliveries.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit changes (`git commit -m "Add feature-name"`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contact

- Support: [support@sendit.com](mailto:muthomiguantai@gmail.com)
- Project Maintainer: MUTHOMIGUANTAI

© 2025 SendIT. All rights reserved. Nairobi, Kenya.
