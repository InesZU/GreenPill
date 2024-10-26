import time
from typing import Optional
from flask import session
from openai.types.beta.threads import Run
from GreenPill_app import threads, client, ASSISTANT_ID
from datamanager.models import User
from extensions import db


def predict(message: str, history: list, request) -> str:
    if 'user_id' not in session:
        raise ValueError("Unauthorized")

    user = db.session.get(User, session['user_id'])
    if not user:
        raise ValueError("User not found")

    session_hash = str(session['user_id'])  # Use user_id as session hash
    MAX_RETRIES = 2
    TIMEOUT = 30  # Increased timeout to 30 seconds
    POLL_INTERVAL = 1  # Poll every 1 second instead of 0.5

    def get_or_create_thread():
        if session_hash in threads:
            return threads[session_hash]['thread']
        thread = client.beta.threads.create()
        threads[session_hash] = {'thread': thread, 'active_run_id': None}
        return thread

    def wait_for_run(thread_id: str, run_id: str) -> Optional[Run]:
        start_time = time.time()
        while True:
            if time.time() - start_time > TIMEOUT:
                raise TimeoutError("Response timeout")

            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)

            if run.status == "completed":
                return run
            elif run.status in ["failed", "cancelled", "expired"]:
                raise Exception(f"Run failed with status: {run.status}")

            time.sleep(POLL_INTERVAL)

    try:
        thread = get_or_create_thread()

        # Add user's allergies and conditions to the message for context
        enhanced_message = (
            f"User context - Allergies: {user.allergies or 'None'}, "
            f"Medical conditions: {user.medical_conditions or 'None'}\n\n"
            f"User message: {message}"
        )

        # Create message
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=enhanced_message
        )

        # Create and monitor run with retries
        for attempt in range(MAX_RETRIES):
            try:
                run = client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=ASSISTANT_ID,
                    instructions=(
                        "Provide concise natural remedy recommendations. "
                        "Consider user's allergies and medical conditions. "
                        "Keep responses under 150 words unless more detail is explicitly requested. "
                        "If you need clarification, ask at most one brief question."
                    )
                )

                threads[session_hash]['active_run_id'] = run.id

                # Wait for completion
                run = wait_for_run(thread.id, run.id)

                # Get latest message
                messages = client.beta.threads.messages.list(thread_id=thread.id)
                if not messages.data:
                    raise ValueError("No response received")

                return messages.data[0].content[0].text.value

            except TimeoutError:
                if attempt == MAX_RETRIES - 1:
                    raise
                # Cancel the current run before retrying
                if threads[session_hash].get('active_run_id'):
                    try:
                        client.beta.threads.runs.cancel(
                            thread_id=thread.id,
                            run_id=threads[session_hash]['active_run_id']
                        )
                    except Exception:
                        pass  # Ignore cancellation errors
                time.sleep(1)  # Brief pause before retry

            finally:
                threads[session_hash]['active_run_id'] = None

    except TimeoutError:
        return ("I apologize, but I'm taking longer than usual to respond. Please try asking your question again, "
                "perhaps in a simpler way.")
    except Exception as e:
        print(f"Error in predict: {e}")
        return "I encountered an error while processing your request. Please try again."