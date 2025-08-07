from flask import Flask
from routes import init_routes
from models import db
from flask_login import LoginManager
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_MAPS_API_KEY'] = os.getenv('GOOGLE_MAPS_API_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sendit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

init_routes(app)

if __name__ == '__main__':
    app.run(debug=True)