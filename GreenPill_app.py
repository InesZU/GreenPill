from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from openai import OpenAI
from datamanager.models import User, Remedy, Complaint, Session, UserRemedy
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from datamanager.SQLite_Data_manager import SQLiteDataManager
from flask_migrate import Migrate
from chat import *
import logging
import uuid

SESSION_FOLDER = 'databases/sessions'  # Root folder for session JSON files
# Ensure the session folder exists
if not os.path.exists(SESSION_FOLDER):
    os.makedirs(SESSION_FOLDER)

load_dotenv()

app = Flask(__name__)
app.config.from_object(os.environ.get('APP_SETTINGS', 'config.DevelopmentConfig'))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///greenpill.sqlite'
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")  # Added a secret key for sessions

# Initialize SQLAlchemy with the app
db.init_app(app)
migrate = Migrate(app, db)

# Initialize data manager
os.makedirs('databases', exist_ok=True)
data_manager = SQLiteDataManager('greenpill.sqlite')
api_key = os.getenv("SECRET_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# Thread storage
threads = {}


def load_data():
    with open('static/data.json', 'r', encoding='utf-8') as file:
        return json.load(file)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/issues')
def issues():
    complaints = load_data().get('complaints', [])
    user_complain = UserRemedy.query.order_by(UserRemedy.timestamp.desc()).all()
    return render_template('issues.html', complaints=complaints, user_complain=user_complain)


@app.route('/remedies')
def remedies():
    herbs = load_data().get('remedies', [])
    user_remedies = UserRemedy.query.order_by(UserRemedy.timestamp.desc()).all()
    return render_template('remedies.html', herbs=herbs, user_remedies=user_remedies)


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
    form = LoginForm()
    user = db.session.get(User, session['user_id'])

    # Check if user exists
    if not user:
        return redirect(url_for('register'))
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            session['user_id'] = user.id  # Set user session
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login failed. Check email and password', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    session_id = request.args.get('session_id')
    sessions = Session.query.filter_by(user_id=user_id).order_by(Session.timestamp.desc()).all()
    history = []

    if session_id:
        chat_session = Session.query.filter_by(session_id=session_id, user_id=user_id).first()
        if chat_session:
            user_folder = get_user_session_folder(user_id)
            session_file_path = os.path.join(user_folder, f"{session_id}.json")

            if os.path.exists(session_file_path):
                with open(session_file_path, 'r') as file:
                    history = json.load(file)

    return render_template('chat.html', sessions=sessions, history=history, session_id=session_id)


# Chat API Route
@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session.get('user_id')
    message = request.json.get('message')

    if not message or not message.strip():
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Handle session data
        current_session_id = session.get('current_session_id')
        session_data = Session.query.filter_by(session_id=current_session_id,
                                               user_id=user_id).first() if current_session_id else None

        # Construct message and response history
        history = []
        if session_data:
            user_folder = get_user_session_folder(user_id)
            session_file_path = os.path.join(user_folder, f"{current_session_id}.json")

            if os.path.exists(session_file_path):
                with open(session_file_path, 'r') as file:
                    history = json.load(file)

        response_text = chat_manager.predict(message, history, request)

        # Update or create session
        if session_data:
            session_data.timestamp = datetime.now()
        else:
            # Create a new session if none exists
            current_session_id = str(uuid.uuid4())
            session_title = chat_manager.generate_session_title(message)

            # Deactivate other active sessions
            Session.query.filter_by(user_id=user_id, active=True).update({'active': False})

            session_data = Session(
                user_id=user_id,
                session_id=current_session_id,
                timestamp=datetime.now(),
                title=session_title,
                active=True
            )
            db.session.add(session_data)
            session['current_session_id'] = current_session_id

        # Update history and save conversation to JSON file
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})

        # Save updated history to JSON file
        user_folder = get_user_session_folder(user_id)
        session_file_path = os.path.join(user_folder, f"{current_session_id}.json")

        with open(session_file_path, 'w') as file:
            json.dump(history, file)

        db.session.commit()

        return jsonify({
            'response': response_text,
            'session_id': session_data.session_id,
            'session_title': session_data.title,
            'timestamp': session_data.timestamp.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        logger.error(f"Error in chat_api: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def get_user_session_folder(user_id):
    """Returns the directory path for a specific user's session files."""
    user_folder = os.path.join(SESSION_FOLDER, str(user_id))
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


@app.route('/sessions', methods=['GET'])
def get_sessions():
    """Retrieve all chat sessions for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user_id = session['user_id']
        sessions = Session.query.filter_by(user_id=user_id).order_by(Session.timestamp.desc()).all()

        sessions_list = [{
            'session_id': s.session_id,
            'title': s.title,
            'timestamp': s.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'active': s.active,
        } for s in sessions]

        return jsonify({'sessions': sessions_list})

    except Exception as e:
        logger.error(f"Error in get_sessions: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/sessions/<session_id>', methods=['POST'])
def reopen_session(session_id):
    """Reopen a specified chat session and retrieve its history from the JSON file."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user_id = session['user_id']
        session_data = Session.query.filter_by(session_id=session_id, user_id=user_id).first()

        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        # Activate the session
        Session.query.filter_by(user_id=user_id, active=True).update({'active': False})
        session_data.active = True
        session['current_session_id'] = session_id
        db.session.commit()

        # Load conversation history from JSON
        user_folder = get_user_session_folder(user_id)
        session_file_path = os.path.join(user_folder, f"{session_id}.json")

        if not os.path.exists(session_file_path):
            return jsonify({'error': 'Session history not found'}), 404

        with open(session_file_path, 'r') as file:
            history = json.load(file)

        return jsonify({
            'session_id': session_id,
            'history': history,
            'session_title': session_data.title,
            'timestamp': session_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logger.error(f"Error in reopen_session: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/sessions/<int:session_id>/activate', methods=['POST'])
def activate_session(session_id):
    # Find the session by session_id
    session = Session.query.filter_by(session_id=session_id).first()

    if session:
        # Set this session as active, and deactivate others for the same user
        data_manager.set_session_active(session.user_id, session_id)
        return jsonify({"message": "Session activated successfully."}), 200
    else:
        return jsonify({"error": "Session not found."}), 404


@app.route('/delete-session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    # Query the session by session_id (assuming 'Session' is your session model)
    session_to_delete = Session.query.filter_by(session_id=session_id).first()

    if session_to_delete:
        try:
            # Delete the session from the database
            db.session.delete(session_to_delete)
            db.session.commit()
            return jsonify({'success': True}), 200
        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            print(e)
            return jsonify({'success': False, 'error': 'Failed to delete session'}), 500
    else:
        return jsonify({'success': False, 'error': 'Session not found'}), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)