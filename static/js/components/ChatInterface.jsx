import React, { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollAreaRef = useRef(null);
  const [lastRequestTime, setLastRequestTime] = useState(0);
  const minRequestInterval = 1000;

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollArea = scrollAreaRef.current;
      scrollArea.scrollTo({
        top: scrollArea.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    console.log("Session ID on load:", sessionId);
    if (sessionId) {
        loadConversation(sessionId);
    }
}, []);

  const loadConversation = async (sessionId) => {
    try {
      const response = await fetch(`/api/chat?session_id=${sessionId}`);
      const data = await response.json();

      if (data.history) {
        const formattedMessages = data.history.map(entry => ({
          content: entry.content,
          role: entry.role,
          timestamp: entry.timestamp || new Date().toISOString()
        }));
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
      setMessages([{
        content: 'Sorry, there was an error loading the previous conversation.',
        role: 'assistant',
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  // Function to delete a previous chat session
function deleteSession(sessionId) {
    if (confirm('Are you sure you want to delete this session?')) {
        // Send DELETE request to the server to delete the session
        fetch(`/delete-session/${sessionId}`, {
            method: 'DELETE', // HTTP method for deletion
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // If successful, remove the session element from the DOM
                const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
                if (sessionElement) {
                    sessionElement.remove();
                }
                alert('Session deleted successfully.');
            } else {
                alert('Error deleting session.');
            }
        })
        .catch(error => {
            console.error('Error deleting session:', error);
            alert('An error occurred while trying to delete the session.');
        });
    }
}

const sendMessage = async (e) => {
    e.preventDefault();
    console.log("sendMessage triggered");
    const now = Date.now();

    // Check if message is empty or if we're still loading
    if (!inputMessage.trim() || isLoading) return;

    // Rate limiting check
    if (now - lastRequestTime < minRequestInterval) {
      // Add a temporary message to show rate limiting
      setMessages(prev => [...prev, {
        content: 'Please wait a moment before sending another message...',
        role: 'system',
        timestamp: new Date().toISOString(),
        temporary: true
      }]);

      // Remove the temporary message after 3 seconds
      setTimeout(() => {
        setMessages(prev => prev.filter(msg => !msg.temporary));
      }, 3000);

      return;
    }

    const newMessage = {
      content: inputMessage,
      role: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, newMessage]);
    setInputMessage('');
    setIsLoading(true);
    setLastRequestTime(now);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          history: messages.filter(msg => msg.role !== 'system'),
        }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();
      setMessages(prev => [...prev, {
        content: data.response,
        role: 'assistant',
        timestamp: new Date().toISOString(),
      }]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        content: 'Sorry, there was an error processing your message.',
        role: 'assistant',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto h-[600px] flex flex-col">
      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        <div className="space-y-4">
          {messages.map((message, index) => (
            <div
              key={`${message.timestamp}-${index}`}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] p-3 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white ml-4'
                    : message.role === 'system'
                    ? 'bg-yellow-100 text-gray-700'
                    : 'bg-gray-100 text-gray-900 mr-4'
                }`}
              >
                {message.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 p-3 rounded-lg mr-4">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
      <CardContent className="p-4 border-t">
        <form onSubmit={sendMessage} className="flex space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message here..."
            className="flex-grow p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <Button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className="px-4"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default ChatInterface;