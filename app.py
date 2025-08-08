from datetime import datetime

import datetimeformat
from flask import Flask
from routes import init_routes
from models import db
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_mail import Mail
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)
socketio = SocketIO(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_MAPS_API_KEY'] = os.getenv('GOOGLE_MAPS_API_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sendit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.jinja_env.filters['datetimeformat'] = datetimeformat
mail = Mail(app)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

def datetimeformat(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value

with app.app_context():
    db.create_all()

init_routes(app)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)