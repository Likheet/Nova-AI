from flask import Flask, render_template, request, jsonify
import requests
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
import sqlite3

load_dotenv()

app = Flask(__name__)
API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Database functions
def init_db():
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats
        (id TEXT PRIMARY KEY,
         title TEXT,
         created_at TIMESTAMP)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         chat_id TEXT,
         role TEXT,
         content TEXT,
         timestamp TIMESTAMP,
         FOREIGN KEY (chat_id) REFERENCES chats (id))
    ''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('chats.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    try:
        db = get_db()
        chats = db.execute('SELECT * FROM chats ORDER BY created_at DESC').fetchall()
        db.close()
        return render_template('index.html', chats=chats)
    except Exception as e:
        print(f"Error in home route: {e}")
        return render_template('index.html', chats=[])

@app.route('/get_chat_history')
def get_chat_history():
    db = get_db()
    chats = db.execute('SELECT * FROM chats ORDER BY created_at DESC').fetchall()
    db.close()
    return jsonify({
        "chats": [{"id": chat['id'], "title": chat['title'], "created_at": chat['created_at']} 
                 for chat in chats]
    })

@app.route('/new_chat', methods=['POST'])
def new_chat():
    chat_id = str(uuid.uuid4())
    title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    db = get_db()
    db.execute('INSERT INTO chats (id, title, created_at) VALUES (?, ?, ?)',
               (chat_id, title, datetime.now().isoformat()))
    db.commit()
    db.close()
    return jsonify({"chat_id": chat_id, "title": title})

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    chat_id = request.json.get('chat_id')
    
    if not chat_id:
        return jsonify({"error": "No chat ID provided"})

    # Save user message to database
    db = get_db()
    db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
               (chat_id, 'user', user_message, datetime.now().isoformat()))
    db.commit()

    # Your existing Perplexity API call code here
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": """You are a friendly and helpful AI assistant named Nova..."""
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "search_domain_filter": None,
        "return_images": False,
        "return_related_questions": False,
        "stream": False
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        bot_response = response.json()["choices"][0]["message"]["content"]
        
        # Save bot response to database
        db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                  (chat_id, 'assistant', bot_response, datetime.now().isoformat()))
        db.commit()
        db.close()
        
        return jsonify({"response": bot_response})
    except Exception as e:
        db.close()
        return jsonify({"error": f"API Error: {str(e)}"})

@app.route('/get_messages/<chat_id>')
def get_messages(chat_id):
    db = get_db()
    messages = db.execute('SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp',
                         (chat_id,)).fetchall()
    db.close()
    return jsonify({"messages": [(msg['role'], msg['content']) for msg in messages]})

@app.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        db = get_db()
        # Delete all messages first due to foreign key constraint
        db.execute('DELETE FROM messages')
        # Then delete all chats
        db.execute('DELETE FROM chats')
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    init_db()
    app.run(debug=True)