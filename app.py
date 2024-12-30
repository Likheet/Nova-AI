from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import os
import requests
import uuid
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
API_KEY = os.getenv("PERPLEXITY_API_KEY")
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')  # Add to .env in production

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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if username already exists
        if cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
            db.close()
            return render_template('register.html', error='Username already exists')
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, hashed_password))
            db.commit()
            db.close()
            return redirect(url_for('login'))
        except Exception as e:
            db.close()
            return render_template('register.html', error=f'Registration failed: {str(e)}')
            
    return render_template('register.html')

@app.route('/')
@login_required
def home():
    try:
        db = get_db()
        user = db.execute('SELECT id FROM users WHERE username = ?', 
                         (session['username'],)).fetchone()
        chats = db.execute('SELECT * FROM chats WHERE user_id = ? ORDER BY created_at DESC',
                          (user['id'],)).fetchall()
        db.close()
        return render_template('index.html', chats=chats, username=session['username'])
    except Exception as e:
        print(f"Error in home route: {e}")
        return render_template('index.html', chats=[], username=session['username'])

@app.route('/get_chat_history')
@login_required
def get_chat_history():
    db = get_db()
    # Get user_id from username
    user = db.execute('SELECT id FROM users WHERE username = ?', 
                     (session['username'],)).fetchone()
    chats = db.execute('SELECT * FROM chats WHERE user_id = ? ORDER BY created_at DESC',
                      (user['id'],)).fetchall()
    db.close()
    return jsonify({
        "chats": [{"id": chat['id'], "title": chat['title'], "created_at": chat['created_at']} 
                 for chat in chats]
    })

@app.route('/update_chat_title/<chat_id>', methods=['POST'])
@login_required
def update_chat_title(chat_id):
    try:
        data = request.get_json()
        title = data.get('title')
        
        db = get_db()
        db.execute('UPDATE chats SET title = ? WHERE id = ?', (title, chat_id))
        db.commit()
        db.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/new_chat', methods=['POST'])
@login_required
def new_chat():
    chat_id = str(uuid.uuid4())
    current_time = datetime.now()
    # Format title with date and time
    title = f"New Chat"
    db = get_db()
    # Get user_id from username
    user = db.execute('SELECT id FROM users WHERE username = ?', 
                     (session['username'],)).fetchone()
    db.execute('INSERT INTO chats (id, title, created_at, user_id) VALUES (?, ?, ?, ?)',
               (chat_id, title, current_time.isoformat(), user['id']))
    db.commit()
    db.close()
    return jsonify({"chat_id": chat_id, "title": title})

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    chat_id = request.json.get('chat_id')
    
    if not chat_id:
        return jsonify({"error": "No chat ID provided"})

    # Get chat history from database
    db = get_db()
    previous_messages = db.execute('''
        SELECT role, content FROM messages 
        WHERE chat_id = ? 
        ORDER BY timestamp''', (chat_id,)).fetchall()

    # Save user message to database
    db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
               (chat_id, 'user', user_message, datetime.now().isoformat()))
    db.commit()

    # Construct messages array with history
    messages = [
        {
            "role": "system",
            "content": """You are a friendly and helpful AI assistant named Nova. 
                        You provide clear, accurate, and helpful responses while 
                        maintaining a friendly and professional tone."""
        }
    ]

    # Add conversation history
    for msg in previous_messages:
        messages.append({
            "role": msg['role'],
            "content": msg['content']
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Perplexity API call
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-huge-128k-online",
        "messages": messages,
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
@login_required
def clear_history():
    try:
        db = get_db()
        user = db.execute('SELECT id FROM users WHERE username = ?', 
                         (session['username'],)).fetchone()
        # Delete messages from user's chats
        db.execute('''DELETE FROM messages WHERE chat_id IN 
                     (SELECT id FROM chats WHERE user_id = ?)''', (user['id'],))
        # Delete user's chats
        db.execute('DELETE FROM chats WHERE user_id = ?', (user['id'],))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    init_db()
    app.run(debug=True)