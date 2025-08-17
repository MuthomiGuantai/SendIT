from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import JSON

def init_models(db):
    class User(db.Model, UserMixin):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password = db.Column(db.String(255), nullable=False)
        is_admin = db.Column(db.Boolean, default=False)
        parcels = db.relationship('Parcel', backref='user', lazy=True)

    class Parcel(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        pickup = db.Column(db.String(255), nullable=False)
        destination = db.Column(db.String(255), nullable=False)
        weight = db.Column(db.Float, nullable=False)
        distance = db.Column(db.Float, nullable=False)
        cost = db.Column(db.Float, nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        tracking_number = db.Column(db.String(16), unique=True, nullable=False)
        status = db.Column(db.String(20), nullable=False, default='Pending')
        current_location = db.Column(db.String(255))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        tracking_history = db.Column(JSON, nullable=False, default=[])
        payments = db.relationship('Payment', backref='parcel', lazy=True)

    class Payment(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        parcel_id = db.Column(db.Integer, db.ForeignKey('parcel.id'), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        amount = db.Column(db.Float, nullable=False)
        phone_number = db.Column(db.String(20), nullable=False)
        status = db.Column(db.String(20), nullable=False, default='pending')
        transaction_id = db.Column(db.String(50))

    return User, Parcel, Payment