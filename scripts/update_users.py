from GreenPill_app import create_app
from datamanager.models import User, db
import json

def update_users():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        for user in users:
            # Set default values for new fields
            if not hasattr(user, 'age'):
                user.age = None
            if not hasattr(user, 'gender'):
                user.gender = None
            if not hasattr(user, 'allergies'):
                user.allergies = json.dumps([])
            if not hasattr(user, 'medical_conditions'):
                user.medical_conditions = json.dumps([])
        
        db.session.commit()

if __name__ == '__main__':
    update_users() 