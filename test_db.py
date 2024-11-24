import os
import sqlite3
from pathlib import Path

def test_db_access():
    # Get the absolute path to the project directory
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    db_path = os.path.join(instance_dir, 'greenpill.db')
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Base directory: {basedir}")
    print(f"Instance directory: {instance_dir}")
    print(f"Database path: {db_path}")
    
    # Check directory existence and permissions
    print("\nChecking directory permissions:")
    print(f"Instance directory exists: {os.path.exists(instance_dir)}")
    if os.path.exists(instance_dir):
        print(f"Instance directory permissions: {oct(os.stat(instance_dir).st_mode)[-3:]}")
    
    # Try to create a test database
    print("\nTrying to create test database:")
    try:
        conn = sqlite3.connect(db_path)
        print("Successfully connected to database")
        conn.close()
        print("Successfully closed database connection")
    except Exception as e:
        print(f"Error connecting to database: {e}")
    
    # Check file permissions if database exists
    if os.path.exists(db_path):
        print(f"\nDatabase file permissions: {oct(os.stat(db_path).st_mode)[-3:]}")

if __name__ == "__main__":
    test_db_access() 