from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from datamanager.models import User, Remedy, Complaint, Session
from datamanager.Data_Maneger import DataManagerInterface
from contextlib import contextmanager
import logging
import sqlite3
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the database engine with WAL mode and retry settings
engine = create_engine(
    "sqlite:///greenpill.sqlite",
    connect_args={
        "check_same_thread": False,  # Allow multithreaded access
        "isolation_level": "AUTOCOMMIT"  # Frequent commits to reduce locking
    }
)


# Enable WAL mode for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()


# Retry mechanism for handling locked database errors
def retry_on_lock(max_attempts=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        attempts += 1
                        logger.warning(f"Database is locked, retrying... (attempt {attempts})")
                        time.sleep(delay)
                    else:
                        raise
            raise sqlite3.OperationalError("Maximum retry attempts exceeded due to database lock.")

        return wrapper

    return decorator


def execute_with_retry():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            connection = sqlite3.connect('greenpill.sqlite')
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            # Your other database operations go here
            connection.commit()
            cursor.close()
            connection.close()
            return  # Successfully completed the transaction
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                time.sleep(1)  # Retry after a short delay
            else:
                raise  # Reraise the error if it's not a lock issue or max retries reached


execute_with_retry()


def set_sqlite_pragma(self):
    """Set the necessary SQLite PRAGMA settings."""
    try:
        connection = sqlite3.connect('greenpill.sqlite',
                                     timeout=10)
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")  # Set WAL mode
        connection.commit()  # Commit the PRAGMA setting
        cursor.close()
        connection.close()
    except sqlite3.OperationalError as e:
        print(f"Error setting PRAGMA: {e}")


class SQLiteDataManager(DataManagerInterface):
    def __init__(self, db_file_name):
        self.engine = create_engine(
            f'sqlite:///{db_file_name}',
            echo=True,
            connect_args={"check_same_thread": False}
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    @retry_on_lock()
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Database error: {e}")
        finally:
            session.close()

    # User management
    def add_user(self, user):
        with self.session_scope() as session:
            session.add(user)

    def get_user(self, user_id):
        with self.session_scope() as session:
            return session.query(User).filter(User.id == user_id).first()

    def get_all_users(self):
        with self.session_scope() as session:
            return session.query(User).all()

    def delete_user(self, user_id):
        with self.session_scope() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                session.delete(user)

    # Remedies management
    def get_remedies(self, limit=10, offset=0):
        with self.session_scope() as session:
            return session.query(Remedy).join(Remedy.complaint).limit(limit).offset(offset).all()

    def get_remedy_by_name(self, name):
        with self.session_scope() as session:
            return session.query(Remedy).filter_by(name=name).first()

    def get_remedies_by_complaint(self, complaint_id):
        with self.session_scope() as session:
            return session.query(Remedy).filter_by(complaint_id=complaint_id).all()

    # Complaints management
    def get_complaints(self, limit=10):
        with self.session_scope() as session:
            return session.query(Complaint).limit(limit).all()

    # Sessions management
    def get_sessions_by_user(self, user_id, limit=10, offset=0, active_only=False):
        with self.session_scope() as session:
            query = session.query(Session).filter_by(user_id=user_id)
            if active_only:
                query = query.filter_by(active=True)
            return query.order_by(Session.timestamp.desc()).limit(limit).offset(offset).all()

    def get_session_history(self, session_id):
        """Retrieve the history of a specific session."""
        with self.session_scope() as session:
            session_data = session.query(Session).filter_by(session_id=session_id).first()
            if session_data:
                messages = session_data.message.split('\n')
                responses = session_data.response.split('\n')
                history = []
                max_length = max(len(messages), len(responses))

                for i in range(max_length):
                    if i < len(messages):
                        history.append({"role": "user", "content": messages[i]})
                    if i < len(responses):
                        history.append({"role": "assistant", "content": responses[i]})
                return history
            return []

    def update_session_title(self, session_id, new_title):
        with self.session_scope() as session:
            session_to_update = session.query(Session).filter_by(session_id=session_id).first()
            if session_to_update:
                session_to_update.title = new_title
                return True
            return False

    def set_session_active(self, user_id, session_id):
        """Sets the requested session as active and deactivates others for the same user."""
        with self.session_scope() as session:
            session.query(Session).filter_by(user_id=user_id, active=True).update({'active': False})
            session_to_activate = session.query(Session).filter_by(session_id=session_id, user_id=user_id).first()
            if session_to_activate:
                session_to_activate.active = True
                return True
            return False

    def delete_session(self, session_id):
        """Delete a session by session ID."""
        with self.session_scope() as session:
            session_to_delete = session.query(Session).filter_by(session_id=session_id).first()
            if session_to_delete:
                session.delete(session_to_delete)
                return True
            return False
