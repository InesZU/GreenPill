from flask import render_template, redirect, url_for, flash, request, session, abort, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datamanager.models import User, Session
from forms.forms import LoginForm, RegistrationForm, ProfileUpdateForm
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from sqlalchemy.exc import IntegrityError
import logging
import traceback
from datetime import timedelta, datetime
from session.session_manager import SessionManager

logger = logging.getLogger(__name__)

def register_routes(app):
    session_manager = SessionManager(app=app)
    
    @app.route('/')
    def home():
        return render_template('pages/home.html')

    @app.route('/chat')
    @app.route('/chat/<session_id>')
    @login_required
    def chat(session_id=None):
        try:
            if session_id:
                # Get existing session
                session = session_manager.get_session(session_id)
                if not session or session.user_id != current_user.id:
                    abort(404)
            else:
                # Only create new session if there's no existing one
                session = None
                messages = []
                
            if session:
                messages = session_manager.get_messages(session_id)
                formatted_messages = [{
                    'content': msg.content,
                    'role': msg.role,
                    'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                } for msg in messages]
            else:
                formatted_messages = []
            
            user_sessions = session_manager.get_user_sessions(current_user.id)
            return render_template('chat/chat.html',
                                 messages=formatted_messages,
                                 sessions=user_sessions,
                                 current_session=session)
        except Exception as e:
            logger.error(f"Error in chat route: {e}")
            flash('Error loading chat session', 'error')
            return redirect(url_for('home'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('chat'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            
            if user and check_password_hash(user.password, form.password.data):
                login_user(user, remember=form.remember.data)
                session.permanent = True
                
                # Update last login
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                flash('Login successful!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('chat'))
            
            flash('Invalid email or password', 'danger')
        
        return render_template('auth/login.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('chat'))
        
        form = RegistrationForm()
        if form.validate_on_submit():
            try:
                # Check for existing user
                if User.query.filter_by(email=form.email.data).first():
                    flash('Email already registered', 'danger')
                    return render_template('auth/register.html', form=form)
                
                if User.query.filter_by(username=form.username.data).first():
                    flash('Username already taken', 'danger')
                    return render_template('auth/register.html', form=form)
                
                # Create new user
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    password=generate_password_hash(form.password.data),
                    age=form.age.data,
                    gender=form.gender.data,
                    allergies=form.allergies.data,
                    medical_conditions=form.medical_conditions.data,
                    created_at=datetime.utcnow()
                )
                
                db.session.add(user)
                db.session.commit()
                
                # Log the user in immediately after registration
                login_user(user, remember=True)
                session.permanent = True
                
                flash('Registration successful! Welcome!', 'success')
                return redirect(url_for('chat'))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f'Registration error: {str(e)}')
                flash('Registration failed. Please try again.', 'danger')
        
        return render_template('auth/register.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        # Clear session data
        session.clear()
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    @app.route('/profile')
    @login_required
    def profile():
        form = ProfileUpdateForm()
        return render_template('pages/profile.html', form=form)

    @app.route('/update_profile', methods=['POST'])
    @login_required
    def update_profile():
        form = ProfileUpdateForm()
        if form.validate_on_submit():
            try:
                # Check if username is taken by another user
                if form.username.data != current_user.username:
                    existing_user = User.query.filter_by(username=form.username.data).first()
                    if existing_user:
                        flash('Username already taken.', 'danger')
                        return redirect(url_for('profile'))

                # Check if email is taken by another user
                if form.email.data != current_user.email:
                    existing_user = User.query.filter_by(email=form.email.data).first()
                    if existing_user:
                        flash('Email already registered.', 'danger')
                        return redirect(url_for('profile'))

                # Update user information
                current_user.username = form.username.data
                current_user.email = form.email.data
                current_user.age = form.age.data
                current_user.gender = form.gender.data
                current_user.allergies = form.allergies.data
                current_user.medical_conditions = form.conditions.data

                db.session.commit()
                flash('Your profile has been updated!', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Profile update error: {str(e)}")
                flash('An error occurred while updating your profile.', 'danger')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
        
        return redirect(url_for('profile'))

    @app.route('/issues')
    @login_required
    def issues():
        return render_template('pages/issues.html')

    @app.route('/remedies')
    @login_required
    def remedies():
        return render_template('pages/remedies.html')

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.before_request
    def before_request():
        if current_user.is_authenticated:
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=31)