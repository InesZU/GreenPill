import logging
import os
import uuid
import json
from datetime import datetime
import openai
from flask import session
from datamanager.models import User, Session, Message
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

    def load_conversation(self, session_id):
        try:
            # Fetch session from database
            chat_session = Session.query.filter_by(session_id=session_id).first()
            if not chat_session:
                return []

            # Load messages from both DB and JSON
            messages = []
            
            # Get messages from database
            db_messages = Message.query.filter_by(session_id=chat_session.id).order_by(Message.timestamp).all()
            for msg in db_messages:
                messages.append({
                    "role": "user" if msg.is_user else "assistant",
                    "content": msg.content
                })

            # Load JSON history if exists
            json_path = f"chat_history/{session_id}.json"
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    json_messages = json.load(f)
                    messages.extend(json_messages)

            return messages

        except Exception as e:
            logger.error(f"Error loading conversation: {str(e)}")
            return []

    def predict(self, message, history=None):
        try:
            # Initialize history if None
            if history is None:
                history = []
            
            # Prepare messages for API call
            messages = [
                {"role": "system", "content": "You are a helpful assistant."}
            ]
            
            # Add history to messages
            for msg in history:
                messages.append(msg)
            
            # Add current message
            messages.append({"role": "user", "content": message})

            # Make API call (synchronous)
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )

            # Get response text
            ai_message = response.choices[0].message.content

            return ai_message

        except Exception as e:
            logger.error(f"Error in predict: {str(e)}")
            raise

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

    def save_message(self, user_id, session_id, content, is_user=True):
        try:
            chat_session = Session.query.filter_by(session_id=session_id).first()
            if not chat_session:
                return
            
            message = Message(
                session_id=chat_session.id,
                content=content,
                is_user=is_user,
                timestamp=datetime.utcnow()
            )
            db.session.add(message)
            db.session.commit()

            # Also save to JSON as backup
            json_path = f"chat_history/{session_id}.json"
            messages = []
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    messages = json.load(f)
            
            messages.append({
                "role": "user" if is_user else "assistant",
                "content": content
            })
            
            with open(json_path, 'w') as f:
                json.dump(messages, f)

        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            db.session.rollback()


# Create a singleton instance
chat_manager = ChatSessionManager()