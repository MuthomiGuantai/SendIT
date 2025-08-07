from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    parcels = db.relationship('Parcel', backref='user', lazy=True)

class Parcel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pickup = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    distance = db.Column(db.Float)
    cost = db.Column(db.Float)
    status = db.Column(db.String(50), nullable=False, default='Pending')
    current_location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)