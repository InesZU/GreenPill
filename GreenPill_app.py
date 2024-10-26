import json
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from extensions import db
from openai import OpenAI
import os
from datamanager.models import User, Remedy, Complaint
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datamanager.SQLite_Data_manager import SQLiteDataManager
from flask_migrate import Migrate
import chat

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
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Changed to OPENAI_API_KEY
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# Thread storage
threads = {}


def load_data():
    with open('static/data.json', 'r', encoding='utf-8') as file:
        return json.load(file)


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/issues')
def issues():
    data = load_data()
    complaints = data.get('complaints', [])
    return render_template('issues.html', complaints=complaints)


@app.route('/remedies')
def remedies():
    data = load_data()
    herbs = data.get('remedies', [])
    return render_template('remedies.html', herbs=herbs)


@app.route('/resources')
def resources():
    return render_template('resources.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if request.method == 'POST':
        print("Form data:", form.data)  # Debug print
        print("Form errors:", form.errors)  # Debug print

        if form.validate_on_submit():
            print("Form validated successfully")  # Debug print
            try:
                hashed_password = generate_password_hash(form.password.data)
                new_user = User()
                db.session.add(new_user)
                db.session.commit()
                flash('Your account has been created! You can now log in.', 'success')
                return redirect(url_for('routes.login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating account: {str(e)}', 'danger')
                print(f"Database error: {e}")  # Debug print
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            session['user_id'] = user.id  # Set user session
            flash('Login successful!', 'success')
            return redirect(url_for('routes.home'))
        else:
            flash('Login failed. Check email and password', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('routes.home'))


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Modern approach to get user
        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404

        message = request.json.get('message')
        history = request.json.get('history')

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        response = chat.predict(message, history, request)
        return jsonify({'response': response})
    except Exception as e:
        print(f"Error in chat: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
