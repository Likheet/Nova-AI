// script.js
let messageContainer = document.getElementById('chat-messages');
let userInput = document.getElementById('user-input');

userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function formatMessage(message) {
    // Remove citation numbers
    message = message.replace(/\[\d+\]/g, '');
    
    // Convert markdown-style bold
    message = message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert numbered lists
    message = message.replace(/(\d+)\.\s/g, '<br><br>$1. ');
    
    // Add paragraph spacing
    message = message.split('\n').map(para => para.trim()).filter(para => para).join(' ');
    
    return message;
}

function appendMessage(message, isUser) {
    // Clear welcome message if it exists
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
        messageDiv.innerHTML = formattedMessage;
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
    if (!message) return;

    appendMessage(message, true);
    userInput.value = '';

    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
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
}