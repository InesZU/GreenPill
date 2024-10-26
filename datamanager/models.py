from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    age = db.Column(db.Integer())
    gender = db.Column(db.String(50))
    allergies = db.Column(db.String(200))
    medical_conditions = db.Column(db.String(200))

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Complaint(db.Model):
    __tablename__ = 'complaint'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(100))
    duration = db.Column(db.String(100))

    # Relationship to remedies
    remedies = db.relationship('Remedy', back_populates='complaint', cascade="all, delete-orphan")


class Remedy(db.Model):
    __tablename__ = 'remedy'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    origin = db.Column(db.String(100), nullable=True)
    medicinal_uses = db.Column(db.Text, nullable=True)
    systems_used_in = db.Column(db.String(100), nullable=True)

    # Foreign key to complaints
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'), nullable=True)
    # Relationship with Complaint, avoiding conflict with Complaint.remedies
    complaint = db.relationship('Complaint', back_populates='remedies')
