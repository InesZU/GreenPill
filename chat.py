import logging
import os
import uuid
import json
from datetime import datetime
import openai
from flask import session
from datamanager.models import User, Session
from extensions import db
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SESSION_FOLDER = "databases/sessions"


def get_user_session_folder(user_id):
    """Return the folder path for storing user session files."""
    user_folder = os.path.join(SESSION_FOLDER, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder


class ChatSessionManager:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=api_key)

    @staticmethod
    def generate_session_title(message: str) -> str:
        """Generate a title for the chat session based on the first message."""
        return f"Chat on {message[:30]}..."

    def _format_conversation_history(self, history: list) -> list:
        """Format the conversation history for OpenAI API."""
        conversation_history = []
        for msg in history:
            if isinstance(msg, str):
                conversation_history.append({"role": "user", "content": msg})
            elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                conversation_history.append(msg)
            else:
                raise ValueError("History format is invalid")
        return conversation_history

    def _handle_session_storage(self, user_id: int, session_id: str, message: str, response_text: str) -> None:
        """Store the chat session in a JSON file with proper formatting."""
        # Define the file path
        user_folder = get_user_session_folder(user_id)
        session_file_path = os.path.join(user_folder, f"{session_id}.json")

        # Load existing conversation if it exists
        history = []
        if os.path.exists(session_file_path):
            try:
                with open(session_file_path, 'r') as file:
                    history = json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to load JSON file {session_file_path}: {e}")
                history = []  # Start with an empty history if loading fails

        # Append new message and response to history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})

        # Save updated history back to JSON file, ensuring proper formatting
        with open(session_file_path, 'w') as file:
            json.dump(history, file, ensure_ascii=False, indent=4)

    def predict(self, message: str, history: list, request) -> str:
        """Process a chat message and return the AI response."""
        if 'user_id' not in session:
            raise ValueError("Unauthorized")

        user_id = session['user_id']
        response_text = None

        try:
            conversation_history = self._format_conversation_history(history)
            conversation_history.append({"role": "user", "content": message})

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversation_history
            )

            response_text = response.choices[0].message.content
            logger.info(f"Response received: {response_text}")

            # Get or create a session in the database
            session_id = session.get('current_session_id')
            if not session_id:
                # Create a new session if one does not exist
                session_id = str(uuid.uuid4())
                session_title = self.generate_session_title(message)

                # Deactivate other active sessions for this user
                new_session = Session(
                    user_id=user_id,
                    session_id=session_id,
                    timestamp=datetime.now(),
                    title=session_title,
                )
                db.session.add(new_session)
                session['current_session_id'] = session_id

            # Save conversation to JSON file
            self._handle_session_storage(user_id, session_id, message, response_text)

            db.session.commit()

        except Exception as e:
            logger.error(f"Error in predict: {e}")
            if isinstance(e, ValueError):
                response_text = "There was a problem with your request. Please try again later."
            elif isinstance(e, ConnectionError):
                response_text = "Unable to connect to the server. Please check your connection."
            else:
                response_text = f"An error occurred: {e}"

        return response_text or "No response available"

    def get_conversation_history(self, session_id: str, user_id: int) -> list:
        """Retrieve conversation history for a given session from JSON file with error handling."""
        user_folder = get_user_session_folder(user_id)
        session_file_path = os.path.join(user_folder, f"{session_id}.json")

        if os.path.exists(session_file_path):
            try:
                with open(session_file_path, 'r') as file:
                    return json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"Error loading conversation history for session {session_id}: {e}")
                return []  # Return an empty history if JSON is invalid
        return []

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """Delete a chat session by session ID and remove the corresponding JSON file."""
        try:
            session_to_delete = Session.query.filter_by(session_id=session_id, user_id=user_id).first()
            if session_to_delete:
                # Delete the session from the database
                db.session.delete(session_to_delete)
                db.session.commit()

                # Delete the JSON file containing the conversation history
                user_folder = get_user_session_folder(user_id)
                session_file_path = os.path.join(user_folder, f"{session_id}.json")
                if os.path.exists(session_file_path):
                    os.remove(session_file_path)

                return True
            else:
                logger.warning(f"Session with ID {session_id} not found for user {user_id}.")
                return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting session: {e}")
            return False


# Create a singleton instance
chat_manager = ChatSessionManager()