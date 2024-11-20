import uuid
from openai import OpenAI
from extensions import db
from datamanager.models import User, Session, Message, Remedy, Complaint
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self):
        self.history = {}
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OpenAI API key not found in environment variables")

    def predict(self, message, history=None):
        try:
            if history is None:
                history = []
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant specializing in natural health remedies and holistic wellness."}
            ]
            
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            messages.append({"role": "user", "content": message})

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )

            ai_message = response.choices[0].message.content
            return ai_message

        except Exception as e:
            logger.error(f"Error in predict: {str(e)}")
            raise

    def extract_health_issues(self, message):
        """Extract health issues from a chat message."""
        try:
            prompt = f"""Analyze this health-related message and extract the main health issues or concerns.
            Message: "{message}"
            
            Return a JSON object with:
            - main_issue: The primary health concern (1-3 words)
            - description: Brief description of the issue
            - related_topics: Array of related health topics"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical issue analyzer. Extract and categorize health concerns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error extracting health issues: {e}")
            return None
        
    def extract_remedies(self, message, response):
        """Extract natural remedies from the chat response."""
        try:
            prompt = f"""Analyze this health-related conversation and extract the suggested natural remedies.
            User Message: "{message}"
            Assistant Response: "{response}"
            
            Return a JSON array of remedies, each containing:
            - name: Name of the remedy (1-3 words)
            - description: Brief description of the remedy
            - usage: How to use/apply the remedy
            - suggested_for: Array of conditions this remedy helps with"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a natural remedy analyzer. Extract and categorize natural health solutions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error extracting remedies: {e}")
            return None

    def generate_session_title(self, message):
        """Generate a concise title from the first message."""
        try:
            prompt = f"""Based on this health-related message: "{message}"
            Generate a very brief 2-3 word title that captures the main health topic or concern.
            Response should be just the title, nothing else.
            Examples:
            - "Headache Relief"
            - "Sleep Issues"
            - "Digestive Health"
            - "Stress Management"
            - "Joint Pain"
            - "Natural Remedies"
            Keep it concise and relevant to natural health."""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical topic summarizer. Create brief, relevant titles for health discussions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=10  # Keep it very short
            )

            title = response.choices[0].message.content.strip()
            
            if len(title) > 30:
                title = title[:27] + "..."
            
            logger.info(f"Generated title: {title}")
            return title

        except Exception as e:
            logger.error(f"Error generating title: {e}")
            return "Health Consultation"  # Fallback title

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
        user_folder = get_user_session_folder(user_id)
        session_file_path = os.path.join(user_folder, f"{session_id}.json")

        history = []
        if os.path.exists(session_file_path):
            try:
                with open(session_file_path, 'r') as file:
                    history = json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to load JSON file {session_file_path}: {e}")
                history = []  # Start with an empty history if loading fails

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})

        with open(session_file_path, 'w') as file:
            json.dump(history, file, ensure_ascii=False, indent=4)

    def load_conversation(self, session_id):
        try:
            chat_session = Session.query.filter_by(session_id=session_id).first()
            if not chat_session:
                return []

            messages = []
            
            db_messages = Message.query.filter_by(session_id=chat_session.id).order_by(Message.timestamp).all()
            for msg in db_messages:
                messages.append({
                    "role": "user" if msg.is_user else "assistant",
                    "content": msg.content
                })

            json_path = f"chat_history/{session_id}.json"
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    json_messages = json.load(f)
                    messages.extend(json_messages)

            return messages

        except Exception as e:
            logger.error(f"Error loading conversation: {str(e)}")
            return []

    

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
                db.session.delete(session_to_delete)
                db.session.commit()

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

    def save_message(self, user_id, session_id, content, role):
        message = Message(
            user_id=user_id,
            session_id=session_id,
            content=content,
            role=role,
            timestamp=datetime.now()
        )
        db.session.add(message)
        db.session.commit()
        return message
    
    def get_or_create_session(self, user_id, session_id=None):
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
                session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    title="New Chat",
                    timestamp=datetime.now()
                )
                db.session.add(session)
                db.session.commit()
                logger.info(f"Created new session: {session_id}")
                return session

            session = Session.query.filter_by(
                session_id=session_id,
                user_id=user_id
            ).first()
            
            if not session:
                session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    title="New Chat",
                    timestamp=datetime.now()
                )
                db.session.add(session)
                db.session.commit()
                logger.info(f"Created new session for existing ID: {session_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            db.session.rollback()
            raise
    
    def load_history(self, user_id, session_id):
        messages = Message.query.filter_by(
            user_id=user_id,
            session_id=session_id
        ).order_by(Message.timestamp).all()
        
        return [msg.to_dict() for msg in messages]

# Create a singleton instance
chat_manager = ChatManager()

def get_user_session_folder(user_id):
    folder = f'chat_sessions/user_{user_id}'
    os.makedirs(folder, exist_ok=True)
    return folder