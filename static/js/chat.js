class ChatManager {
    constructor() {
        // Initialize DOM elements
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.chatMessages = document.getElementById('chat-messages');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.chatContainer = document.getElementById('chat-container');
        this.sessionsList = document.getElementById('sessions-list');

        // Track current session
        this.currentSessionId = null;

        this.bindEvents();
        this.loadInitialHistory();
        this.fetchSessionsList();
        this.bindDeleteButtons();
    }

    bindEvents() {
        if (this.sendButton && this.messageInput) {
            this.sendButton.addEventListener('click', () => this.handleSendMessage());

            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey && !this.messageInput.disabled) {
                    e.preventDefault();
                    this.handleSendMessage();
                }
            });

            this.messageInput.focus();
        }

        if (this.sessionsList) {
        this.sessionsList.addEventListener('click', (e) => {
            const target = e.target;

            if (target.classList.contains('btn-reopen')) {
                const sessionId = target.getAttribute('data-session-id');
                if (sessionId) {
                    this.reopenSession(sessionId);
                }
            }

            if (target.classList.contains('btn-delete')) {
                const sessionId = target.getAttribute('data-session-id');
                if (sessionId) {
                    this.deleteSession(sessionId);
                }
            }
        });
    }
}

    loadInitialHistory() {
        const existingMessages = this.chatMessages.querySelectorAll('.message');
        if (existingMessages.length > 0) {
            const urlParams = new URLSearchParams(window.location.search);
            this.currentSessionId = urlParams.get('session_id');
        }
    }

    updateSessionsList(sessions) {
        if (!this.sessionsList) return;

        this.sessionsList.innerHTML = '';

        sessions.forEach(session => {
            const sessionDiv = document.createElement('div');
            sessionDiv.className = 'session-item';

            if (session.session_id === this.currentSessionId) {
                sessionDiv.classList.add('active');
            }

            sessionDiv.innerHTML = `
                <div class="session-info">
                    <h3>${session.title}</h3>
                    <p>${session.timestamp}</p>
                </div>
                <div class="session-actions">
                    <button class="btn-reopen" data-session-id="${session.session_id}">
                        Open
                    </button>
                    <button class="btn-delete" data-session-id="${session.session_id}">
                        Delete
                    </button>
                </div>
            `;
            this.sessionsList.appendChild(sessionDiv);
        });
    }

    async handleSendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        try {
            this.setLoadingState(true);
            this.addMessage(message, true);
            this.messageInput.value = '';

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message,
                    session_id: this.currentSessionId || null
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to send message');
            }

            this.addMessage(data.response, false);

            if (data.session_id && !this.currentSessionId) {
                this.currentSessionId = data.session_id;
                const newUrl = new URL(window.location);
                newUrl.searchParams.set('session_id', data.session_id);
                window.history.pushState({}, '', newUrl);

                await this.fetchSessionsList();
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('Sorry, there was an error processing your request.', false);
        } finally {
            this.setLoadingState(false);
        }
    }

    async fetchSessionsList() {
        try {
            const response = await fetch('/api/sessions');
            const sessions = await response.json();
            this.updateSessionsList(sessions);
        } catch (error) {
            console.error("Error loading sessions:", error);
        }
    }

    async reopenSession(sessionId) {
    try {
        const response = await fetch(`/sessions/${current_user.id}/${sessionId}`, {
            method: 'POST'
        });

        const data = await response.json();
        if (response.ok) {
            window.location.href = `/chat?session_id=${data.session_id}`;
        } else {
            throw new Error(data.error || 'Failed to reopen session');
        }
    } catch (error) {
        console.error("Error reopening session:", error);
        alert("Failed to reopen session. Please try again.");
    }
}

bindDeleteButtons() {
        // Add click event listeners to all delete buttons
        document.querySelectorAll('.btn-delete').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const sessionId = button.getAttribute('data-session-id');
                if (sessionId) {
                    this.deleteSession(sessionId);
                }
            });
        });
    }
    async deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this session?')) return;

        try {
            const response = await fetch(`/api/sessions/${sessionId}/delete`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (response.ok) {
                // Remove the session element from the DOM
                const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
                if (sessionElement) {
                    sessionElement.remove();
                }

                // If we're in the deleted session, redirect to /chat
                if (sessionId === this.currentSessionId) {
                    window.location.href = '/chat';
                }
            } else {
                throw new Error(data.message || 'Failed to delete session');
            }
        } catch (error) {
            console.error('Error deleting session:', error);
            alert('Failed to delete session. Please try again.');
        }
    }
}

    addMessage(content, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (Array.isArray(content)) {
            content.forEach(segment => {
                const segmentDiv = document.createElement('div');

                if (segment.type === 'text') {
                    segmentDiv.textContent = segment.content;
                } else if (segment.type === 'heading') {
                    segmentDiv.innerHTML = `<strong>${segment.content}</strong>`;
                } else if (segment.type === 'list') {
                    const list = document.createElement('ul');
                    segment.content.forEach(item => {
                        const listItem = document.createElement('li');
                        listItem.textContent = item;
                        list.appendChild(listItem);
                    });
                    segmentDiv.appendChild(list);
                }

                contentDiv.appendChild(segmentDiv);
            });
        } else {
            contentDiv.textContent = content;
        }

        messageDiv.appendChild(contentDiv);
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    setLoadingState(isLoading) {
        if (this.messageInput && this.sendButton && this.typingIndicator) {
            this.messageInput.disabled = isLoading;
            this.sendButton.disabled = isLoading;
            this.typingIndicator.style.display = isLoading ? 'flex' : 'none';
            if (!isLoading) this.messageInput.focus();
        }
    }
}

// Initialize chat manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const chatManager = new ChatManager();
    window.chatManager = chatManager;  // Make it globally accessible
});