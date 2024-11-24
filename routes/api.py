from flask import jsonify, request, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFProtect
from extensions import db
import logging
from datamanager.models import Session, Message
from chat.chat_manager import ChatManager
from chat.chat_manager import init_chat_manager

logger = logging.getLogger(__name__)
csrf = CSRFProtect()

# Create a single instance of ChatManager
chat_manager = ChatManager()

def register_api_routes(app):
    csrf.init_app(app)

    chat_manager = init_chat_manager(app)

    @app.route('/api/chat', methods=['POST'])
    @login_required
    def chat_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            message = data.get('message')
            session_id = data.get('session_id')
            
            if not message:
                return jsonify({'error': 'No message provided'}), 400
                
            logger.info(f"Received message from user {current_user.id}: {message}")
            
            if not session_id:
                session_id = chat_manager.get_or_create_session(current_user.id)
                
            response = chat_manager.get_response(session_id, message)
            return jsonify({'response': response, 'session_id': session_id})
            
        except Exception as e:
            logger.error(f"Error in chat API: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/chat/history', methods=['GET'])
    @login_required
    def chat_history():
        try:
            session_id = request.args.get('session_id')
            if not session_id:
                return jsonify({'error': 'Session ID is required'}), 400

            messages = chat_manager.load_history(current_user.id, session_id)
            return jsonify({'messages': messages})

        except Exception as e:
            logger.error(f"Chat history error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sessions', methods=['GET'])
    @login_required
    def get_sessions():
        try:
            sessions = Session.query.filter_by(
                user_id=current_user.id
            ).order_by(Session.timestamp.desc()).all()
            
            return jsonify({
                'sessions': [{
                    'id': session.session_id,
                    'title': session.title,
                    'timestamp': session.timestamp.strftime('%Y-%m-%d %H:%M')
                } for session in sessions]
            })

        except Exception as e:
            logger.error(f"Get sessions error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/session/rename', methods=['POST'])
    @login_required
    def rename_session():
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            new_title = data.get('title')

            if not session_id or not new_title:
                return jsonify({'error': 'Session ID and title are required'}), 400

            session = Session.query.filter_by(
                session_id=session_id,
                user_id=current_user.id
            ).first()

            if not session:
                return jsonify({'error': 'Session not found'}), 404

            session.title = new_title
            db.session.commit()

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Rename session error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/session/delete/<session_id>', methods=['DELETE'])
    @login_required
    def delete_session(session_id):
        try:
            logger.info(f"Attempting to delete session {session_id}")
            session = Session.query.filter_by(
                session_id=session_id,
                user_id=current_user.id
            ).first()
            
            if not session:
                logger.warning(f"Session {session_id} not found")
                return jsonify({'error': 'Session not found'}), 404
                
            # Delete all messages in the session
            message_count = Message.query.filter_by(session_id=session.id).delete()
            logger.info(f"Deleted {message_count} messages from session {session_id}")
            
            # Delete the session
            db.session.delete(session)
            db.session.commit()
            
            logger.info(f"Successfully deleted session {session_id}")
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Delete session error: {e}")
            db.session.rollback()
            return jsonify({'error': str(e)}), 500