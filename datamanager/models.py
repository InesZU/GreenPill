import uuid
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    allergies = db.Column(db.String(500), nullable=True)
    medical_conditions = db.Column(db.String(500), nullable=True)

    # Sessions relationship
    sessions = db.relationship('Session', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")

    def __init__(self):
        self.password_hash = None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Complaint(db.Model):
    __tablename__ = 'complaint'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(100))
    duration = db.Column(db.String(100))

    # Remedies relationship
    remedies = db.relationship('Remedy', back_populates='complaint', cascade="all, delete-orphan")


class Remedy(db.Model):
    __tablename__ = 'remedy'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    origin = db.Column(db.String(100))
    medicinal_uses = db.Column(db.Text)
    systems_used_in = db.Column(db.String(100))

    # Foreign key and relationship to Complaint
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'))
    complaint = db.relationship('Complaint', back_populates='remedies')


class Session(db.Model):
    __tablename__ = 'session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255))

    # User relationship
    user = db.relationship('User', back_populates='sessions')


class UserRemedy(db.Model):
    __tablename__ = 'user_remedy'

    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    remedy_details = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)