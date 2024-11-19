import json
import uuid
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import current_user, login_required, LoginManager, logout_user, login_user
from flask_limiter.util import get_remote_address
from chat import chat_manager, get_user_session_folder
from datamanager.models import User, Remedy, Session, UserRemedy
from extensions import db
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from datetime import timedelta, datetime
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(os.getenv('APP_SETTINGS', 'config.DevelopmentConfig'))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///greenpill.sqlite'
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


def load_data():
    with open('static/data.json', 'r', encoding='utf-8') as file:
        return json.load(file)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if request.method == 'POST':
        logging.debug("Form data: %s", form.data)
        logging.debug("Form errors: %s", form.errors)

        if form.validate_on_submit():
            logging.debug("Form validated successfully")
            # Check if email already exists
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered. Please log in.', 'danger')
                return render_template('register.html', form=form)

            try:
                hashed_password = generate_password_hash(form.password.data)
                new_user = User(
                    username=form.username.data,
                    email=form.email.data,
                    password=hashed_password,
                    age=form.age.data,
                    gender=form.gender.data,
                    allergies=form.allergies.data,
                    medical_conditions=form.conditions.data
                )
                db.session.add(new_user)
                db.session.commit()
                flash('Your account has been created! You can now log in.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating account: {str(e)}', 'danger')
                logging.error("Database error: %s", e)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user, remember=form.remember.data)
                # Add user_id to the session
                session['user_id'] = user.id
                flash('Login successful!', 'success')
                return redirect(url_for('chat'))
            else:
                flash('Invalid email or password.', 'danger')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/issues')
def issues():
    complaints = load_data().get('complaints', [])
    user_complain = UserRemedy.query.order_by(UserRemedy.timestamp.desc()).all()
    return render_template('issues.html', complaints=complaints, user_complain=user_complain)


@app.route('/remedies')
def remedies():
    remedies = Remedy.query.all()
    return render_template('remedies.html', remedies=remedies)


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            # Use the exact file path structure you confirmed
            file_path = f"databases/sessions/{user_id}/{session_id}.json"
            
            chat_history = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    chat_history = json.load(f)
                    print(f"Loaded chat history: {chat_history}")  # Debug print
            
            session['current_session_id'] = session_id
            return render_template('chat.html', 
                                 history=chat_history,  # Pass the full history
                                 sessions=Session.query.filter_by(user_id=user_id).all())
                                 
        except Exception as e:
            print(f"Error: {str(e)}")
            return redirect(url_for('chat'))

    return render_template('chat.html',
                         history=[],
                         sessions=Session.query.filter_by(user_id=user_id).all())


@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    try:
        message = request.json.get('message', '').strip()
        session_id = request.json.get('session_id')

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Get or create session
        if session_id:
            chat_session = Session.query.filter_by(
                session_id=session_id,
                user_id=current_user.id
            ).first()
        else:
            session_id = str(uuid.uuid4())
            chat_session = Session(
                session_id=session_id,
                user_id=current_user.id,
                timestamp=datetime.now(),
                title=chat_manager.generate_session_title(message)
            )
            db.session.add(chat_session)

        # Load or initialize history
        user_folder = get_user_session_folder(current_user.id)
        session_file_path = os.path.join(user_folder, f"{session_id}.json")

        if os.path.exists(session_file_path):
            with open(session_file_path, 'r') as file:
                history = json.load(file)
        else:
            history = []

        # Generate response - fixed argument count
        response_text = chat_manager.predict(message, history)  # Removed the request argument

        # Update session
        chat_session.timestamp = datetime.now()
        db.session.commit()

        # Update and save history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})

        # Ensure the user folder exists
        os.makedirs(os.path.dirname(session_file_path), exist_ok=True)
        
        # Save the updated history
        with open(session_file_path, 'w') as file:
            json.dump(history, file)

        return jsonify({
            'response': response_text,
            'session_id': chat_session.session_id,
            'session_title': chat_session.title,
            'timestamp': chat_session.timestamp.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}")
    return render_template('500.html'), 500


# Add this new route to handle session deletion
@app.route('/api/sessions/<session_id>/delete', methods=['DELETE'])
@login_required
def delete_session(session_id):
    try:
        # Find the session in SQL database
        chat_session = Session.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not chat_session:
            return jsonify({'error': 'Session not found'}), 404

        # Delete the JSON file from user's folder
        user_folder = f"databases/sessions/{current_user.id}"
        json_file = f"{session_id}.json"
        file_path = os.path.join(user_folder, json_file)
        
        # Delete JSON file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted JSON file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting JSON file: {e}")
                return jsonify({'error': 'Failed to delete session file'}), 500

        # Delete from SQL database
        try:
            db.session.delete(chat_session)
            db.session.commit()
            logger.info(f"Deleted session from database: {session_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error: {e}")
            return jsonify({'error': 'Failed to delete session from database'}), 500

        return jsonify({'message': 'Session deleted successfully'})

    except Exception as e:
        logger.error(f"Error in delete_session: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
    