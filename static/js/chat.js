document.addEventListener('DOMContentLoaded', function() {
    const messagesContainer = document.querySelector('#chat-messages');
    const messageInput = document.querySelector('#message-input');
    const sendButton = document.querySelector('#send-button');
    const typingIndicator = document.querySelector('#typing-indicator');

    if (!messagesContainer || !messageInput || !sendButton || !typingIndicator) {
        console.error('Some elements were not found. Check your HTML IDs.');
        return;
    }

    let isRequestInProgress = false;
    const minRequestInterval = 1000;
    let lastRequestTime = 0;

    function addMessage(content, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
        messageDiv.textContent = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function hideTypingIndicator() {
        typingIndicator.style.display = 'none';
    }

    function showTemporaryMessage(message) {
        const statusDiv = document.createElement('div');
        statusDiv.className = 'status-message';
        statusDiv.textContent = message;
        messagesContainer.appendChild(statusDiv);

        setTimeout(() => {
            statusDiv.remove();
        }, 3000);
    }

    function showTypingIndicator() {
        typingIndicator.style.display = 'block';
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // Ensure a minimum interval between requests
        const now = Date.now();
        if (isRequestInProgress || now - lastRequestTime < minRequestInterval) {
            showTemporaryMessage('Please wait a moment before sending another message...');
            return;
        }

        try {
            isRequestInProgress = true;
            lastRequestTime = now;

            // Disable input and send button while processing
            messageInput.value = '';
            messageInput.disabled = true;
            sendButton.disabled = true;

            addMessage(message, true);
            showTypingIndicator();

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    history: []
                })
            });

            const data = await response.json();

            if (data.error) {
                addMessage('Sorry, there was an error processing your message.', false);
            } else {
                addMessage(data.response, false);
            }

        } catch (error) {
            console.error('Error in sendMessage:', error);
            addMessage('Sorry, there was an error processing your message.', false);
        } finally {
            hideTypingIndicator();
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.focus();
            isRequestInProgress = false;
        }
    }

    sendButton.addEventListener('click', (e) => {
        e.preventDefault();
        sendMessage();
    });

    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    messageInput.focus();
});