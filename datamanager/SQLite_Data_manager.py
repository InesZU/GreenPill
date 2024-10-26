from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datamanager.models import User, Remedy, Complaint
from datamanager.Data_Maneger import DataManagerInterface
from contextlib import contextmanager


class SQLiteDataManager(DataManagerInterface):
    def __init__(self, db_file_name):
        self.engine = create_engine(f'sqlite:///{db_file_name}')
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error: {e}")
        finally:
            session.close()

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

    def get_remedies(self, limit=10, offset=0):
        with self.session_scope() as session:
            return session.query(Remedy).join(Remedy.complaint).limit(limit).offset(offset).all()

    def get_remedy_by_name(self, name):
        with self.session_scope() as session:
            return session.query(Remedy).filter_by(name=name).first()

    def get_remedies_by_complaint(self, complaint_id):
        with self.session_scope() as session:
            return session.query(Remedy).filter_by(complaint_id=complaint_id).all()

    def get_complaints(self, limit=10):
        with self.session_scope() as session:
            return session.query(Complaint).limit(limit).all()