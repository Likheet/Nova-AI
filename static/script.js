// script.js
let messageContainer = document.getElementById('chat-messages');
let userInput = document.getElementById('user-input');
let currentChatId = null;

userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

async function createNewChat() {
    // Check if there's an existing chat that's empty
    if (currentChatId) {
        // Get messages for current chat
        const response = await fetch(`/get_messages/${currentChatId}`);
        const data = await response.json();
        
        // If current chat has no messages, don't create a new one
        if (data.messages.length === 0) {
            return;
        }
    }

    try {
        const response = await fetch('/new_chat', {
            method: 'POST'
        });
        const data = await response.json();
        currentChatId = data.chat_id;
        await loadChatHistory();
        clearMessages();
    } catch (error) {
        console.error('Error creating new chat:', error);
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Wrap createNewChat with debounce
const debouncedCreateNewChat = debounce(createNewChat, 300);

async function loadChatHistory() {
    try {
        const response = await fetch('/get_chat_history');
        const data = await response.json();
        displayChatHistory(data.chats);
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

function displayChatHistory(chats) {
    const historyContainer = document.getElementById('chat-history');
    historyContainer.innerHTML = '';
    
    chats.forEach(chat => {
        const chatElement = document.createElement('div');
        chatElement.className = 'chat-history-item';
        if (chat.id === currentChatId) {
            chatElement.classList.add('active');
        }
        chatElement.onclick = () => loadChat(chat.id);
        
        const date = new Date(chat.created_at);
        chatElement.innerHTML = `
            <div class="chat-title">${chat.title}</div>
            <div class="chat-date">${date.toLocaleDateString()}</div>
        `;
        historyContainer.appendChild(chatElement);
    });
}

async function loadChat(chatId) {
    currentChatId = chatId;
    try {
        const response = await fetch(`/get_messages/${chatId}`);
        const data = await response.json();
        displayMessages(data.messages);
        highlightActiveChat();
    } catch (error) {
        console.error('Error loading chat:', error);
    }
}

function highlightActiveChat() {
    document.querySelectorAll('.chat-history-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.chatId === currentChatId) {
            item.classList.add('active');
        }
    });
}

function displayMessages(messages) {
    messageContainer.innerHTML = '';
    messages.forEach(msg => {
        appendMessage(msg[1], msg[0] === 'user');
    });
}

function clearMessages() {
    messageContainer.innerHTML = `
        <div class="welcome-message">
            <h1>Nova AI Assistant</h1>
            <p>How can I help you today?</p>
        </div>
    `;
}

async function clearChatHistory() {
    if (!confirm('Are you sure you want to clear all chat history?')) {
        return;
    }
    
    try {
        const response = await fetch('/clear_history', {
            method: 'POST'
        });
        
        if (response.ok) {
            const historyContainer = document.getElementById('chat-history');
            historyContainer.innerHTML = '';
            currentChatId = null;
            clearMessages();
        } else {
            console.error('Failed to clear chat history');
        }
    } catch (error) {
        console.error('Error clearing chat history:', error);
    }
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.innerHTML = 'Nova is thinking...';
    messageContainer.appendChild(loadingDiv);
}
function handleError(error) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `Error: ${error} <button onclick="retryLastMessage()">Retry</button>`;
    messageContainer.appendChild(errorDiv);
}

function formatMessage(message) {
    // Remove citation numbers
    message = message.replace(/\[\d+\]/g, '');
    
    // Convert Markdown-style bold
    message = message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert Markdown-style italic
    message = message.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Convert line breaks and paragraphs
    message = message.split('\n').map(para => `<p>${para.trim()}</p>`).join('');
    
    return message;
}

function appendMessage(message, isUser) {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    if (isUser) {
        messageDiv.textContent = message;
    } else {
        const formattedMessage = formatMessage(message);
        messageDiv.innerHTML = formattedMessage; // Safely inject formatted content
    }
    
    messageContainer.appendChild(messageDiv);
    messageContainer.scrollTop = messageContainer.scrollHeight;
}

function newChat() {
    messageContainer.innerHTML = `
        <div class="welcome-message">
            <h1>Nova AI Assistant</h1>
            <p>How can I help you today?</p>
        </div>
    `;
    userInput.value = '';
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!currentChatId) {
        await createNewChat();
    }
    if (!message) return;

    appendMessage(message, true);
    userInput.value = '';

    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                message: message,
                chat_id: currentChatId 
            })
        });

        const data = await response.json();
        
        if (data.error) {
            appendMessage('Error: ' + data.error, false);
        } else {
            appendMessage(data.response, false);
        }
    } catch (error) {
        appendMessage('Error: Could not connect to the server', false);
    }
    document.addEventListener('DOMContentLoaded', () => {
        loadChatHistory();
    });
}
