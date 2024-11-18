import sqlite3
import json
import os
from datetime import datetime, timedelta
import threading
from typing import Optional, Dict, Any, Union
import uuid
import logging
from pathlib import Path
from flask_login import current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionManager:
    """
    Session manager that can store sessions in either SQLite or JSON.
    Includes automatic cleanup of expired sessions and thread-safe operations.
    """

    def __init__(self, storage_type: str = 'sqlite',
                 storage_path: str = 'sessions',
                 session_lifetime: int = 24, user_id=None):
        """
        Initialize the session manager.

        Args:
            storage_type: 'sqlite' or 'json'
            storage_path: Directory/file path for storage
            session_lifetime: Session lifetime in hours
        """
        self.user_id = user_id
        self.storage_type = storage_type.lower()
        self.session_lifetime = timedelta(hours=session_lifetime)
        self.lock = threading.Lock()

        if self.storage_type == 'sqlite':
            self.db_path = 'instance/greenpill.sqlite'
            self._init_sqlite()
        else:
            self.json_path = os.path.join('databases', 'sessions', str(user_id), f"{storage_path}.json")
            logger.info(f"JSON Path: {self.json_path}")
            self._init_json()

        # Start cleanup thread
        self._start_cleanup_thread()

    def _init_sqlite(self):
        """Initialize SQLite database with sessions table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        last_accessed TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON sessions(expires_at)')
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    def _init_json(self):
        """Initialize JSON storage file."""
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        if not os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'w') as f:
                    json.dump({}, f)
            except Exception as e:
                logger.error(f"Failed to initialize JSON storage: {e}")
                raise

    def create_session(self, user_id: int, data: Dict[str, Any] = None) -> str:
        """
        Create a new session.

        Args:
            user_id: User ID associated with the session
            data: Additional session data

        Returns:
            session_id: Unique session identifier
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + self.session_lifetime

        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'data': data or {},
            'created_at': now.isoformat(),
            'last_accessed': now.isoformat(),
            'expires_at': expires_at.isoformat()
        }

        with self.lock:
            if self.storage_type == 'sqlite':
                self._save_session_sqlite(session_data)
            else:
                self._save_session_json(session_data)

        return session_id

    def _save_session_sqlite(self, session_data: dict):
        """Save session to SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO sessions 
                    (session_id, user_id, data, created_at, last_accessed, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    session_data['session_id'],
                    session_data['user_id'],
                    json.dumps(session_data['data']),
                    session_data['created_at'],
                    session_data['last_accessed'],
                    session_data['expires_at']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save session to SQLite: {e}")
            raise

    def _save_session_json(self, session_data: dict):
        """Save session to JSON file."""
        try:
            with open(self.json_path, 'r+') as f:
                data = json.load(f)
                data[session_data['session_id']] = session_data
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.error(f"Failed to save session to JSON: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found/expired
        """
        with self.lock:
            if self.storage_type == 'sqlite':
                return self._get_session_sqlite(session_id)
            return self._get_session_json(session_id)

    def _get_session_sqlite(self, session_id: str) -> Optional[dict]:
        """Retrieve session from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT user_id, data, created_at, last_accessed, expires_at
                    FROM sessions
                    WHERE session_id = ? AND expires_at > ?
                ''', (session_id, datetime.utcnow().isoformat()))

                row = cursor.fetchone()
                if row:
                    # Update last accessed time
                    conn.execute('''
                        UPDATE sessions 
                        SET last_accessed = ? 
                        WHERE session_id = ?
                    ''', (datetime.utcnow().isoformat(), session_id))
                    conn.commit()

                    return {
                        'session_id': session_id,
                        'user_id': row[0],
                        'data': json.loads(row[1]),
                        'created_at': row[2],
                        'last_accessed': row[3],
                        'expires_at': row[4]
                    }
        except Exception as e:
            logger.error(f"Failed to retrieve session from SQLite: {e}")
        return None

    def _get_session_json(self, session_id: str) -> Optional[dict]:
        """Retrieve session from JSON file."""
        try:
            with open(self.json_path, 'r+') as f:
                data = json.load(f)
                session = data.get(session_id)

                if session and datetime.fromisoformat(session['expires_at']) > datetime.utcnow():
                    # Update last accessed time
                    session['last_accessed'] = datetime.utcnow().isoformat()
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()
                    return session
        except Exception as e:
            logger.error(f"Failed to retrieve session from JSON: {e}")
        return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if session was deleted, False otherwise
        """
        with self.lock:
            if self.storage_type == 'sqlite':
                return self._delete_session_sqlite(session_id)
            return self._delete_session_json(session_id)

    def _delete_session_sqlite(self, session_id: str) -> bool:
        """Delete session from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete session from SQLite: {e}")
            return False

    def _delete_session_json(self, session_id: str) -> bool:
        """Delete session from JSON file."""
        try:
            # Ensure the path exists
            if not os.path.exists(os.path.dirname(self.json_path)):
                logger.error(f"Directory path {os.path.dirname(self.json_path)} does not exist.")
                return False

            if not os.path.exists(self.json_path):
                logger.error(f"Session file {self.json_path} does not exist.")
                return False

            with open(self.json_path, 'r+') as f:
                data = json.load(f)
                if session_id in data:
                    logger.info(f"Deleting session {session_id} from JSON.")
                    del data[session_id]
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()
                    logger.info(f"Session {session_id} deleted from JSON successfully.")
                    return True
                else:
                    logger.warning(f"Session {session_id} not found in JSON.")
                    return False
        except Exception as e:
            logger.error(f"Failed to delete session {session_id} from JSON: {e}")
            return False

    def cleanup_expired_sessions(self):
        """Remove all expired sessions."""
        with self.lock:
            if self.storage_type == 'sqlite':
                self._cleanup_expired_sqlite()
            else:
                self._cleanup_expired_json()

    def _cleanup_expired_sqlite(self):
        """Clean up expired sessions from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM sessions WHERE expires_at < ?',
                             (datetime.utcnow().isoformat(),))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions from SQLite: {e}")

    def _cleanup_expired_json(self):
        """Clean up expired sessions from JSON file."""
        try:
            with open(self.json_path, 'r+') as f:
                data = json.load(f)
                current_time = datetime.utcnow()
                data = {
                    sid: session for sid, session in data.items()
                    if datetime.fromisoformat(session['expires_at']) > current_time
                }
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions from JSON: {e}")

    def _start_cleanup_thread(self):
        """Start a background thread for cleaning up expired sessions."""

        def cleanup_task():
            while True:
                self.cleanup_expired_sessions()
                # Run cleanup every hour
                threading.Event().wait(3600)

        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()


# Example usage
if __name__ == '__main__':
    user_id = getattr(current_user, 'id', None)

    # Example with SQLite storage
    sqlite_manager = SessionManager(storage_type='sqlite', storage_path='greenpill', user_id=user_id)

    # Create a session
    user_data = {
        'name': 'John Doe',
        'role': 'user',
        'preferences': {'theme': 'dark'}
    }
    session_id = sqlite_manager.create_session(user_id=123, data=user_data)
    print(f"Created session: {session_id}")

    # Retrieve session
    session = sqlite_manager.get_session(session_id)
    print(f"Retrieved session: {session}")

    # Delete session
    deleted = sqlite_manager.delete_session(session_id)
    print(f"Deleted session: {deleted}")

    user_id = getattr(current_user, 'id', None)
    # Example with JSON storage
    json_manager = SessionManager(storage_type='json', storage_path='sessions_id', user_id=user_id)

    # Create a session
    session_id = json_manager.create_session(user_id=456, data=user_data)
    print(f"Created JSON session: {session_id}")

    # Retrieve session
    session = json_manager.get_session(session_id)
    print(f"Retrieved JSON session: {session}")

    # Delete session
    deleted = json_manager.delete_session(session_id)
    print(f"Deleted JSON session: {deleted}")