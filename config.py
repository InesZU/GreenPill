import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Get the absolute path to the instance folder
    INSTANCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    
    # Ensure instance folder exists
    os.makedirs(INSTANCE_PATH, exist_ok=True)
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(INSTANCE_PATH, "greenpill.sqlite")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Other configurations
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ASSISTANT_ID = os.getenv('ASSISTANT_ID')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    pass


class TestingConfig(Config):
    TESTING = True