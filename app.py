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
@login_required
def send_message():
    data = request.json
    user_message = data.get('message')
    chat_id = data.get('chat_id')

    if not chat_id or not user_message:
        return jsonify({"error": "Chat ID and message are required"}), 400

    with get_db() as db:
        # Save user message
        db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                   (chat_id, 'user', user_message, datetime.now().isoformat()))
        db.commit()

    # Prepare API payload
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {"role": "system", "content": "You are a friendly assistant. Respond to all inputs in a conversational manner, avoiding definitions or disambiguations."},
            {"role": "user", "content": user_message}
        ],
        "temperature": 1.0,
        "top_p": 0.9,
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Log the payload for debugging
    print("Sending request to Perplexity API:")
    print(payload)

    try:
        # Make API request
        response = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
        print("API response status code:", response.status_code)  # Log status code
        print("Raw API response content:", response.text)  # Log raw response content
        response.raise_for_status()
        response_data = response.json()

        # Log parsed response for debugging
        print("Parsed API response data:", response_data)

        # Extract bot's response
        bot_response = response_data["choices"][0]["message"]["content"]

        # Save bot response
        with get_db() as db:
            db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                       (chat_id, 'assistant', bot_response, datetime.now().isoformat()))
            db.commit()

        return jsonify({"response": bot_response})
    except requests.exceptions.RequestException as e:
        print("RequestException occurred:", e)  # Log exception details
        return jsonify({"error": f"API request failed: {e}"}), 500
    except KeyError as e:
        print("KeyError in API response:", e)  # Log KeyError details
        return jsonify({"error": "Unexpected API response format"}), 500
    except Exception as e:
        print("Unexpected error:", e)  # Log any other unexpected errors
        return jsonify({"error": "An unexpected error occurred"}), 500

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