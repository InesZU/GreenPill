import json
import uuid
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import current_user, login_required, LoginManager, logout_user, login_user
from flask_limiter.util import get_remote_address
from chat import chat_manager, get_user_session_folder
from datamanager.models import User, Remedy, Session, Complaint
from extensions import db
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from datetime import timedelta, datetime
import logging
import os
from dotenv import load_dotenv
from werkzeug.urls import url_parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create instance directory if it doesn't exist
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Initialize Flask app
app = Flask(__name__, instance_relative_config=True)
app.config.from_object(os.getenv('APP_SETTINGS', 'config.DevelopmentConfig'))

# Ensure instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Update database URI to use absolute path
db_path = os.path.join(app.instance_path, 'greenpill.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.init_app(app)

# Update your CSRF configuration
# csrf = CSRFProtect(app)

# Add this before your routes
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-CSRFToken')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


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
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Check if user already exists
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already registered. Please login.', 'danger')
                return redirect(url_for('login'))
            
            # Create new user
            hashed_password = generate_password_hash(form.password.data)
            user = User(
                username=form.username.data,
                email=form.email.data,
                password_hash=hashed_password
            )
            
            # Add user to database
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'danger')
            
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user, remember=form.remember.data)
                
                # Get next page from URL parameters, or default to home
                next_page = request.args.get('next')
                if not next_page or url_parse(next_page).netloc != '':
                    next_page = url_for('home')
                    
                flash('Login successful!', 'success')
                return redirect(next_page)
            else:
                flash('Invalid email or password', 'danger')
                
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
@login_required
def issues():
    # Get user's issues sorted by frequency
    user_issues = Complaint.query.filter_by(user_id=current_user.id)\
        .order_by(Complaint.frequency.desc())\
        .all()
    
    # Get related sessions for each issue
    issues_data = []
    for issue in user_issues:
        related_sessions = []
        if issue.related_sessions:
            session_ids = json.loads(issue.related_sessions)
            related_sessions = Session.query.filter(
                Session.session_id.in_(session_ids)
            ).all()
            
        issues_data.append({
            'issue': issue,
            'sessions': related_sessions
        })
    
    return render_template('issues.html', issues_data=issues_data)


@app.route('/remedies')
@login_required
def remedies():
    # Get user's remedies sorted by frequency
    user_remedies = Remedy.query.filter_by(user_id=current_user.id)\
        .order_by(Remedy.times_suggested.desc())\
        .all()
    
    # Get related sessions for each remedy
    remedies_data = []
    for remedy in user_remedies:
        related_sessions = []
        if remedy.related_sessions:
            session_ids = json.loads(remedy.related_sessions)
            related_sessions = Session.query.filter(
                Session.session_id.in_(session_ids)
            ).all()
            
        suggested_for = json.loads(remedy.suggested_for) if remedy.suggested_for else []
            
        remedies_data.append({
            'remedy': remedy,
            'sessions': related_sessions,
            'conditions': suggested_for
        })
    
    return render_template('remedies.html', remedies_data=remedies_data)


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    logger.info("Chat route accessed")
    session_id = request.args.get('session_id')
    history = []
    
    if session_id:
        logger.info(f"Loading session: {session_id}")
        # Load existing session
        chat_session = Session.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if chat_session:
            try:
                history = chat_manager.load_history(current_user.id, session_id)
                logger.info(f"History loaded: {len(history)} messages")
            except Exception as e:
                logger.error(f"Error loading chat history: {e}")
                flash('Failed to load chat history', 'error')
    
    # Get all sessions for the sidebar
    sessions = Session.query.filter_by(user_id=current_user.id)\
        .order_by(Session.timestamp.desc())\
        .all()
    logger.info(f"Found {len(sessions)} sessions")
    
    return render_template('chat.html',
                         history=history,
                         sessions=sessions,
                         session_id=session_id,
                         current_time=datetime.now())


@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id')

        # Load chat history if session_id exists
        history = []
        if session_id:
            history = chat_manager.load_history(current_user.id, session_id)
            logger.info(f"Loaded history for session {session_id}: {len(history)} messages")

        # Get chatbot response
        response_text = chat_manager.predict(message, history)

        # Create or get session
        chat_session = chat_manager.get_or_create_session(current_user.id, session_id)
        
        # Save messages
        chat_manager.save_message(current_user.id, chat_session.session_id, message, 'user')
        chat_manager.save_message(current_user.id, chat_session.session_id, response_text, 'assistant')

        return jsonify({
            'response': response_text,
            'session_id': chat_session.session_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}")
    return render_template('500.html'), 500


# Add this new route to handle session deletion
@app.route('/api/sessions/<session_id>', methods=['DELETE'])  # Simplified URL
@login_required
def delete_session(session_id):
    logger.info(f"Delete request received for session: {session_id}")
    try:
        # Find the session in SQL database
        chat_session = Session.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not chat_session:
            logger.error(f"Session not found: {session_id}")
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


@app.route('/api/sessions/verify/<session_id>')
@login_required
def verify_session(session_id):
    try:
        chat_session = Session.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if chat_session:
            return jsonify({
                'exists': True,
                'title': chat_session.title,
                'timestamp': chat_session.timestamp.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'exists': False}), 404
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions', methods=['GET'])
@login_required
def get_sessions():
    try:
        sessions = Session.query.filter_by(user_id=current_user.id)\
            .order_by(Session.timestamp.desc())\
            .all()
        
        return jsonify([{
            'id': session.session_id,
            'title': session.title,
            'timestamp': session.timestamp.strftime('%Y-%m-%d %H:%M')
        } for session in sessions])
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        return jsonify({'error': 'Failed to fetch sessions'}), 500


# Add this after all routes are defined
def list_routes():
    logger.info("Available routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"{rule.rule} [{', '.join(rule.methods)}]")


# Call this when the app starts
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        list_routes()  # Log all available routes
    app.run(debug=True)
    
@app.context_processor
def utility_processor():
    return {
        'now': datetime.now
    }