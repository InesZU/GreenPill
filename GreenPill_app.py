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
    return User.query.get(int(user_id))


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
@login_required
def chat():
    try:
        # Handle POST requests (e.g., deleting a session)
        if request.method == 'POST' and 'delete_session_id' in request.form:
            delete_session_id = request.form['delete_session_id']
            chat_session = Session.query.filter_by(
                session_id=delete_session_id,
                user_id=current_user.id
            ).first()

            if chat_session:
                session_file_path = os.path.join(
                    get_user_session_folder(current_user.id),
                    f"{delete_session_id}.json"
                )

                # Delete session file
                if os.path.exists(session_file_path):
                    os.remove(session_file_path)

                # Delete session record from the database
                db.session.delete(chat_session)
                db.session.commit()
                flash('Session deleted successfully.', 'success')
            else:
                flash('Session not found.', 'danger')

            return redirect(url_for('chat'))

        # Handle GET requests (loading chat history and sessions)
        session_id = request.args.get('session_id')  # Extract session ID from query parameters
        sessions = Session.query.filter_by(user_id=current_user.id).order_by(Session.timestamp.desc()).all()
        history = []

        if session_id:
            chat_session = Session.query.filter_by(
                session_id=session_id,
                user_id=current_user.id
            ).first_or_404()

            session_file_path = os.path.join(
                get_user_session_folder(current_user.id),
                f"{session_id}.json"
            )

            if os.path.exists(session_file_path):
                with open(session_file_path, 'r') as file:
                    history = json.load(file)
            else:
                flash('Session file not found.', 'warning')

        return render_template('chat.html', sessions=sessions, history=history, session_id=session_id)

    except Exception as e:
        logger.error(f"Error loading chat: {e}")
        flash('Error loading chat session.', 'danger')
        return redirect(url_for('home'))


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

        # Generate response
        response_text = chat_manager.predict(message, history, request)

        # Update session
        chat_session.timestamp = datetime.now()
        db.session.commit()

        # Update and save history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})

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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
