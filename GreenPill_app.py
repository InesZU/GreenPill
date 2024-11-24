from datetime import datetime
import sys
from pathlib import Path
from flask_login import LoginManager
from flask_migrate import Migrate
from datamanager.models import User, init_db
sys.path.append(str(Path(__file__).parent))
from flask import Flask, jsonify
from extensions import db, login_manager
from config import Config
import logging
import os
from pathlib import Path
from flask_session import Session
from datetime import timedelta
from flask_wtf.csrf import CSRFProtect, CSRFError
from dotenv import load_dotenv

# Load environment variables at the start
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    
    # Check for required environment variables
    required_vars = ['OPENAI_API_KEY', 'ASSISTANT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Add this near the top of your configuration
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # or some number of seconds
    
    # Strong secret key
    app.config['SECRET_KEY'] = os.urandom(24)
    
    # Session configuration
    app.config.update(
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(app.instance_path, 'flask_session'),
        PERMANENT_SESSION_LIFETIME=timedelta(days=31),
        SESSION_PERMANENT=True,
        REMEMBER_COOKIE_DURATION=timedelta(days=31),
        REMEMBER_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )
    
    Session(app)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(app.instance_path, "greenpill.sqlite")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Login manager configuration
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        return jsonify({
            'error': 'CSRF token validation failed',
            'message': str(e)
        }), 400

    with app.app_context():
        init_db(app)
        
        from routes.main import register_routes
        from routes.api import register_api_routes
        
        register_routes(app)
        register_api_routes(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)