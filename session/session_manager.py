from datetime import datetime, timedelta
import threading
import uuid
import logging
from typing import Optional, Dict, Any
import json
from flask_login import current_user
from flask import current_app
from extensions import db
from datamanager.models import Session, Message, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, session_lifetime: int = 24, app=None):
        """
        Initialize the session manager.
        Args:
            session_lifetime: Session lifetime in hours
            app: Flask application instance
        """
        self.session_lifetime = timedelta(hours=session_lifetime)
        self.lock = threading.Lock()
        self.app = app
        self._start_cleanup_thread()

    def create_session(self, user_id: int, title: str = "New Chat", data: Dict[str, Any] = None) -> str:
        """Create a new chat session."""
        try:
            session_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            new_session = Session(
                session_id=session_id,
                user_id=user_id,
                title=title,
                topic=data.get('topic') if data else None,
                symptoms_discussed=json.dumps(data.get('symptoms', [])) if data else None,
                remedies_suggested=json.dumps(data.get('remedies', [])) if data else None,
                created_at=now,
                updated_at=now
            )
            
            with self.lock:
                db.session.add(new_session)
                db.session.commit()
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            db.session.rollback()
            raise

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        try:
            with self.lock:
                session = Session.query.filter_by(session_id=session_id).first()
                if session:
                    session.updated_at = datetime.utcnow()
                    db.session.commit()
                return session
        except Exception as e:
            logger.error(f"Failed to retrieve session: {e}")
            return None

    def add_message(self, session_id: str, content: str, role: str, 
                   remedies_mentioned: list = None, issues_mentioned: list = None) -> bool:
        """Add a message to a session."""
        try:
            with self.lock:
                session = Session.query.filter_by(session_id=session_id).first()
                if not session:
                    return False
                
                message = Message(
                    session_id=session.id,
                    content=content,
                    role=role,
                    remedies_mentioned=json.dumps(remedies_mentioned) if remedies_mentioned else None,
                    issues_mentioned=json.dumps(issues_mentioned) if issues_mentioned else None,
                    timestamp=datetime.utcnow()
                )
                
                db.session.add(message)
                session.updated_at = datetime.utcnow()
                db.session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            db.session.rollback()
            return False

    def get_messages(self, session_id: str) -> list:
        """Get all messages for a session."""
        try:
            session = Session.query.filter_by(session_id=session_id).first()
            if session:
                return Message.query.filter_by(session_id=session.id)\
                    .order_by(Message.timestamp.asc())\
                    .all()
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve messages: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        try:
            with self.lock:
                session = Session.query.filter_by(session_id=session_id).first()
                if session:
                    Message.query.filter_by(session_id=session.id).delete()
                    db.session.delete(session)
                    db.session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            db.session.rollback()
            return False

    def get_user_sessions(self, user_id: int) -> list:
        """Get all sessions for a user."""
        try:
            return Session.query.filter_by(user_id=user_id)\
                .order_by(Session.updated_at.desc())\
                .all()
        except Exception as e:
            logger.error(f"Failed to retrieve user sessions: {e}")
            return []

    def update_session_title(self, session_id: str, new_title: str) -> bool:
        """Update a session's title."""
        try:
            with self.lock:
                session = Session.query.filter_by(session_id=session_id).first()
                if session:
                    session.title = new_title
                    session.updated_at = datetime.utcnow()
                    db.session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")
            db.session.rollback()
            return False

    def cleanup_expired_sessions(self):
        """Remove sessions older than session_lifetime."""
        try:
            # Create an application context
            with self.app.app_context():
                with self.lock:
                    expiry_date = datetime.utcnow() - self.session_lifetime
                    expired_sessions = Session.query.filter(Session.updated_at < expiry_date).all()
                    
                    for session in expired_sessions:
                        Message.query.filter_by(session_id=session.id).delete()
                        db.session.delete(session)
                    
                    db.session.commit()
                    logger.info(f"Cleaned up sessions older than {expiry_date}")
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            if self.app:
                with self.app.app_context():
                    db.session.rollback()

    def _start_cleanup_thread(self):
        """Start a background thread for cleaning up expired sessions."""
        if not self.app:
            logger.warning("No Flask app provided, cleanup thread not started")
            return

        def cleanup_task():
            while True:
                try:
                    self.cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
                finally:
                    threading.Event().wait(3600)  # Run cleanup every hour

        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        logger.info("Cleanup thread started")