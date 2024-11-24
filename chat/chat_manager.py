from flask import current_app
from flask_login import current_user
from openai import OpenAI
import os
import logging
import time
from datetime import datetime
import uuid
from session.session_manager import SessionManager
from datamanager.models import Session, Message
from extensions import db
import json

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self, app=None):
        self.app = app
        self.session_manager = SessionManager(app=app)
        
        # Get API credentials with error checking
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.assistant_id = os.getenv('ASSISTANT_ID')
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        if not self.assistant_id:
            raise ValueError("ASSISTANT_ID not found in environment variables")
            
        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"ChatManager initialized with Assistant ID: {self.assistant_id}")

    def get_response(self, session_id: str, user_message: str):
        try:
            # Get or create session
            session = self.session_manager.get_session(session_id)
            if not session:
                session_id = self.session_manager.create_session(user_id=current_user.id)
                session = self.session_manager.get_session(session_id)

            # Save user message
            self.session_manager.add_message(
                session_id=session_id,
                content=user_message,
                role="user"
            )

            # Get AI response
            response = self.predict(user_message, session_id)
            
            if response:
                # Save AI response
                self.session_manager.add_message(
                    session_id=session_id,
                    content=response,
                    role="assistant"
                )

                # Generate title for new sessions
                if session.title == "New Chat":
                    title = self.generate_title(session_id)
                    if title:
                        self.session_manager.update_session_title(session_id, title)

                return response
            
            return None

        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            return None

    def predict(self, message, session_id=None):
        try:
            logger.info(f"Creating thread with Assistant ID: {self.assistant_id}")
            
            # Get context from previous interactions if session exists
            context = ""
            if session_id:
                messages = self.session_manager.get_messages(session_id)
                if messages:
                    context = "Previous conversation:\n" + "\n".join([
                        f"{msg.role.capitalize()}: {msg.content}"
                        for msg in messages[-5:]  # Last 5 messages
                    ]) + "\n\nCurrent message:\n"
            
            full_message = f"{context}{message}" if context else message
            
            # Create thread and get response from OpenAI
            thread = self.client.beta.threads.create()
            logger.info(f"Created thread: {thread.id}")
            
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=full_message
            )
            logger.info(f"Added message to thread {thread.id}")
            
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id  # This should now be properly set
            )
            logger.info(f"Started run {run.id} with assistant {self.assistant_id}")
            
            # Wait for completion with timeout
            max_retries = 30  # 30 seconds timeout
            retries = 0
            while retries < max_retries:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logger.error(f"Assistant run failed with status: {run_status}")
                    raise Exception(f"Assistant run failed: {run_status.last_error}")
                retries += 1
                time.sleep(1)
            
            if retries >= max_retries:
                raise Exception("Assistant response timed out")
            
            # Get response
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            for message in messages:
                if message.role == "assistant":
                    return message.content[0].text.value
                    
            raise Exception("No assistant response found")
            
        except Exception as e:
            logger.error(f"Error in predict: {str(e)}")
            raise

    def get_or_create_session(self, user_id, session_id=None):
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session and session.user_id == user_id:
                return session

        # Create new session
        return self.session_manager.create_session(
            user_id=user_id,
            title="New Chat"
        )

    def get_chat_history(self, user_id, session_id=None):
        if session_id:
            return self.session_manager.get_messages(session_id)
        else:
            return self.session_manager.get_user_sessions(user_id)

    def update_session_title(self, session_id: str, new_title: str):
        return self.session_manager.update_session_title(session_id, new_title)

    def generate_title(self, session_id: str) -> str:
        """Generate a title based on the conversation content."""
        try:
            messages = self.session_manager.get_messages(session_id)
            if not messages:
                return None

            # Create a prompt for title generation
            conversation_summary = "\n".join([
                f"{msg.role}: {msg.content[:100]}..."  # First 100 chars of each message
                for msg in messages[:2]  # Use first two messages
            ])

            thread = self.client.beta.threads.create()
            
            # Add the prompt for title generation
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Based on this conversation, generate a brief, descriptive title (max 6 words):\n\n{conversation_summary}"
            )

            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )

            # Wait for completion
            max_retries = 10
            retries = 0
            while retries < max_retries:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                if run_status.status == 'completed':
                    messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                    for message in messages:
                        if message.role == "assistant":
                            title = message.content[0].text.value.strip('" ')
                            return title[:50]  # Limit title length
                elif run_status.status == 'failed':
                    break
                retries += 1
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error generating title: {e}")
        
        return None

# Create a single instance
chat_manager = None

def init_chat_manager(app):
    global chat_manager
    if chat_manager is None:
        chat_manager = ChatManager(app=app)
    return chat_manager 