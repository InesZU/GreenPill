class ChatManager {
    constructor() {
        console.log('ChatManager: Constructor started');
        
        // Get CSRF token from meta tag
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (!csrfMeta) {
            console.error('CSRF token meta tag not found');
            return;
        }
        this.csrfToken = csrfMeta.content;
        
        // Initialize DOM elements
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.chatMessages = document.getElementById('chat-messages');
        this.typingIndicator = document.getElementById('typing-indicator');
        
        // Get current session ID
        this.currentSessionId = document.getElementById('current-session-id')?.value || null;
        
        // Initialize
        this.bindEvents();
        this.bindSessionEvents();
        this.loadInitialMessages();
        
        // Add welcome message if no initial messages
        if (!window.initialMessages || !window.initialMessages.length) {
            this.addMessageToChat(
                "Hello! I'm Sina, your natural remedies assistant. I'm here to help you discover the healing power of herbs and natural medicines. What would you like to know about?",
                'assistant'
            );
        }
    }

    bindEvents() {
        console.log('ChatManager: Binding events');
        if (this.sendButton) {
            this.sendButton.onclick = () => {
                console.log('ChatManager: Send button clicked');
                this.handleSendMessage();
            };
        }
        
        if (this.messageInput) {
            this.messageInput.onkeypress = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    console.log('ChatManager: Enter pressed');
                    e.preventDefault();
                    this.handleSendMessage();
                }
            };
        }
    }

    async handleSendMessage() {
        console.log('ChatManager: handleSendMessage called');
        const message = this.messageInput.value.trim();
        if (!message) {
            console.log('ChatManager: Empty message, returning');
            return;
        }

        try {
            console.log('ChatManager: Processing message:', message);
            
            // Show typing indicator
            if (this.typingIndicator) {
                this.typingIndicator.style.display = 'flex';
            }

            // Add user message to chat
            this.addMessageToChat(message, 'user');

            // Clear input
            this.messageInput.value = '';

            // Use the current session ID when sending messages
            const response = await this.sendMessage(message, this.currentSessionId);
            console.log('ChatManager: Server response:', response);

            // Hide typing indicator
            if (this.typingIndicator) {
                this.typingIndicator.style.display = 'none';
            }

            // Add AI response to chat
            if (response && response.response) {
                this.addMessageToChat(response.response, 'assistant');
            }

        } catch (error) {
            console.error('ChatManager: Error in handleSendMessage:', error);
            alert('Failed to send message. Please try again.');
        }
    }

    addMessageToChat(content, role) {
        console.log('ChatManager: Adding message to chat:', { role });
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        // Add herb icon for assistant messages
        if (role === 'assistant') {
            messageDiv.innerHTML = `
                <div class="message-icon">🌿</div>
                <div class="message-content">${content}</div>
            `;
        } else {
            messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
        }
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    async sendMessage(message, sessionId = null) {
        console.log('ChatManager: Sending message to server:', { message, sessionId });
        
        if (!this.csrfToken) {
            console.error('CSRF token not found');
            throw new Error('CSRF token missing');
        }

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'include',  // Important for CSRF
                body: JSON.stringify({ 
                    message,
                    session_id: sessionId 
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server returned ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error sending message:', error);
            throw error;
        }
    }

    // Add method to format herbal recommendations
    formatHerbalRecommendation(content) {
        // Add special formatting for herb names and dosages
        return content.replace(/\b(tea|tincture|extract|capsule|powder)\b/gi, '<span class="dosage-form">$1</span>')
                     .replace(/\b(\d+(?:-\d+)?\s*(?:mg|ml|g|oz|cups?))\b/gi, '<span class="dosage">$1</span>');
    }

    bindSessionEvents() {
        // Reopen button handlers
        document.querySelectorAll('.reopen-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const sessionId = button.dataset.sessionId;
                window.location.href = `/chat/${sessionId}`;
            });
        });

        // Delete button handlers
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                e.preventDefault();
                const sessionId = button.dataset.sessionId;
                
                if (!confirm('Are you sure you want to delete this chat session?')) {
                    return;
                }

                try {
                    const response = await fetch(`/api/session/delete/${sessionId}`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': this.csrfToken,
                            'Content-Type': 'application/json'
                        },
                        credentials: 'include'
                    });

                    if (response.ok) {
                        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
                        if (sessionElement) {
                            sessionElement.remove();
                        }
                        
                        // If we're in the deleted session, redirect to /chat
                        if (this.currentSessionId === sessionId) {
                            window.location.href = '/chat';
                        }
                    } else {
                        alert('Failed to delete session. Please try again.');
                    }
                } catch (error) {
                    console.error('Error deleting session:', error);
                    alert('Failed to delete session. Please try again.');
                }
            });
        });
    }

    loadInitialMessages() {
        try {
            if (window.initialMessages && Array.isArray(window.initialMessages)) {
                window.initialMessages.forEach(msg => {
                    this.addMessageToChat(msg.content, msg.role);
                });
            }
        } catch (e) {
            console.error('Error loading initial messages:', e);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing ChatManager');
    window.chatManager = new ChatManager();
});

// Add a global error handler
window.onerror = function(msg, url, line, col, error) {
    console.error('Global error:', {
        message: msg,
        url: url,
        line: line,
        column: col,
        error: error
    });
    return false;
};