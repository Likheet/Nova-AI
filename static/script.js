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
        chatElement.dataset.chatId = chat.id;
        chatElement.onclick = () => loadChat(chat.id);
        
        if (chat.id === currentChatId) {
            chatElement.classList.add('active');
        }

        const titleDiv = document.createElement('div');
        titleDiv.className = 'chat-title';
        titleDiv.textContent = chat.title || 'New Chat';
        
        const dateDiv = document.createElement('div');
        dateDiv.className = 'chat-date';
        
        if (chat.title) {
            const date = new Date(chat.created_at);
            const formatNumber = (n) => n.toString().padStart(2, '0');
            const formattedDate = `${formatNumber(date.getDate())}-${formatNumber(date.getMonth() + 1)}-${date.getFullYear()} ${formatNumber(date.getHours())}:${formatNumber(date.getMinutes())}`;
            dateDiv.textContent = formattedDate;
        }
        
        chatElement.appendChild(titleDiv);
        chatElement.appendChild(dateDiv);
        historyContainer.appendChild(chatElement);
    });
}
function copyCode(button) {
    const codeBlock = button.previousElementSibling;
    const code = codeBlock.textContent;
    
    navigator.clipboard.writeText(code).then(() => {
        button.textContent = 'Copied!';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.textContent = 'Copy';
            button.classList.remove('copied');
        }, 2000);
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

async function updateChatTitle(chatId, firstMessage) {
    // Truncate long messages and clean up special characters
    let title = firstMessage
        .split(' ')
        .slice(0, 6)
        .join(' ')
        .replace(/[^\w\s]/gi, '')
        .trim();
    
    if (title.length > 30) {
        title = title.substring(0, 30) + '...';
    }

    try {
        const response = await fetch(`/update_chat_title/${chatId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title })
        });
        
        if (response.ok) {
            await loadChatHistory(); // Refresh chat list
        }
    } catch (error) {
        console.error('Error updating chat title:', error);
    }
}

function highlightActiveChat() {
    document.querySelectorAll('.chat-history-item').forEach(item => {
        item.classList.remove('active');
        // Convert both to strings for comparison
        if (item.dataset.chatId.toString() === currentChatId.toString()) {
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
    const markedOptions = {
        breaks: true,
        gfm: true,
        sanitize: true
    };

    let parts = [];
    let currentIndex = 0;
    const codeBlockRegex = /```([\w-]*)\n([\s\S]*?)```/g;

    // Find and process code blocks
    let match;
    while ((match = codeBlockRegex.exec(message)) !== null) {
        // Add text before code block (processed with marked)
        if (match.index > currentIndex) {
            let textPart = message.slice(currentIndex, match.index);
            parts.push(marked.parse(textPart, markedOptions));
        }

        // Add custom formatted code block
        const language = match[1];
        const code = match[2].trim();
        parts.push(`
            <div class="code-block">
                ${language ? `<div class="code-header">${language}</div>` : ''}
                <pre><code class="${language}">${code}</code></pre>
                <button class="copy-button" onclick="copyCode(this)">Copy</button>
            </div>
        `);

        currentIndex = match.index + match[0].length;
    }

    // Add remaining text (processed with marked)
    if (currentIndex < message.length) {
        parts.push(marked.parse(message.slice(currentIndex), markedOptions));
    }

    return parts.join('');
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
            <h1 class="typing-effect">Nova AI Assistant</h1>
            <p class="typing-effect delayed-typing">How can I help you today?</p>
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

    // Add loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message';
    loadingDiv.innerHTML = '<div class="loading-message">Nova is thinking</div>';
    messageContainer.appendChild(loadingDiv);
    messageContainer.scrollTop = messageContainer.scrollHeight;

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
        
        // Remove loading indicator
        loadingDiv.remove();

        // Update chat title after first message
        const messagesCount = document.querySelectorAll('.message').length;
        if (messagesCount === 1) {
            await updateChatTitle(currentChatId, message);
        }

        if (data.error) {
            appendMessage('Error: ' + data.error, false);
        } else {
            appendMessage(data.response, false);
        }
    } catch (error) {
        // Remove loading indicator
        loadingDiv.remove();
        appendMessage('Error: Could not connect to the server', false);
    }
}