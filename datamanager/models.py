from datetime import datetime
from extensions import db
from flask_login import UserMixin
import uuid
import json

# Association tables
user_remedies = db.Table('user_remedies',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('remedy_id', db.Integer, db.ForeignKey('remedies.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

issue_remedies = db.Table('issue_remedies',
    db.Column('issue_id', db.Integer, db.ForeignKey('issues.id'), primary_key=True),
    db.Column('remedy_id', db.Integer, db.ForeignKey('remedies.id'), primary_key=True),
    db.Column('effectiveness', db.Integer)  # Scale of 1-5
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    # Personal Information
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    
    # Medical Information
    allergies = db.Column(db.Text)
    medical_conditions = db.Column(db.Text)
    medications = db.Column(db.Text)
    
    # Preferences
    preferred_remedies = db.Column(db.Text)  # JSON string of preferred remedy types
    dietary_restrictions = db.Column(db.Text)
    
    # Timestamps and Status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    sessions = db.relationship('Session', backref='user', lazy=True)
    issues = db.relationship('Issue', backref='user', lazy=True)
    saved_remedies = db.relationship('Remedy', secondary=user_remedies, lazy='subquery',
        backref=db.backref('users', lazy=True))

    def __repr__(self):
        return f'<User {self.username}>'

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), default="New Chat")
    
    # Session Details
    topic = db.Column(db.String(100))
    symptoms_discussed = db.Column(db.Text)  # JSON string of symptoms
    remedies_suggested = db.Column(db.Text)  # JSON string of remedy IDs
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('Message', backref='session', lazy=True)

    def __repr__(self):
        return f'<Session {self.session_id}>'

    def save_message(self, content: str, role: str, 
                    remedies_mentioned: list = None, 
                    issues_mentioned: list = None) -> 'Message':
        """Save a new message to this session."""
        message = Message(
            session_id=self.id,
            content=content,
            role=role,
            remedies_mentioned=json.dumps(remedies_mentioned) if remedies_mentioned else None,
            issues_mentioned=json.dumps(issues_mentioned) if issues_mentioned else None,
            timestamp=datetime.utcnow()
        )
        db.session.add(message)
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return message

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Message Metadata
    remedies_mentioned = db.Column(db.Text)  # JSON string of remedy IDs
    issues_mentioned = db.Column(db.Text)    # JSON string of issue IDs

class Issue(db.Model):
    __tablename__ = 'issues'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Issue Details
    severity = db.Column(db.Integer)  # Scale of 1-5
    frequency = db.Column(db.String(50))  # e.g., "daily", "weekly"
    duration = db.Column(db.String(50))   # e.g., "2 hours", "3 days"
    triggers = db.Column(db.Text)         # JSON string of known triggers
    
    # Tracking
    status = db.Column(db.String(20), default='active')  # active, resolved, monitoring
    first_reported = db.Column(db.DateTime, default=datetime.utcnow)
    last_occurred = db.Column(db.DateTime)
    resolution_date = db.Column(db.DateTime)
    
    # Relationships
    remedies = db.relationship('Remedy', secondary=issue_remedies, lazy='subquery',
        backref=db.backref('issues', lazy=True))

    def __repr__(self):
        return f'<Issue {self.title}>'

class Remedy(db.Model):
    __tablename__ = 'remedies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Remedy Details
    category = db.Column(db.String(50))  # e.g., "herb", "exercise", "diet"
    preparation = db.Column(db.Text)     # How to prepare/use
    dosage = db.Column(db.Text)         # Recommended dosage
    warnings = db.Column(db.Text)       # Contraindications and warnings
    
    # Scientific Information
    scientific_name = db.Column(db.String(100))
    benefits = db.Column(db.Text)        # JSON string of known benefits
    side_effects = db.Column(db.Text)    # JSON string of potential side effects
    interactions = db.Column(db.Text)    # JSON string of known interactions
    
    # Usage Statistics
    times_suggested = db.Column(db.Integer, default=0)
    effectiveness_rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_suggested = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Remedy {self.name}>'

# Create database tables
def init_db(app):
    with app.app_context():
        db.create_all()
