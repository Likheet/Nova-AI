from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import os
import requests
import uuid
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from werkzeug.utils import secure_filename
import PyPDF2
import io

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Add this line
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

# Database functions
def init_db():
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE NOT NULL,
                 password TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                (id TEXT PRIMARY KEY,
                 title TEXT,
                 created_at TIMESTAMP,
                 user_id INTEGER,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 chat_id TEXT,
                 role TEXT,
                 content TEXT,
                 timestamp TIMESTAMP,
                 FOREIGN KEY (chat_id) REFERENCES chats (id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 filename TEXT NOT NULL,
                 content TEXT NOT NULL,
                 upload_date TIMESTAMP,
                 user_id INTEGER,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
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

# ...existing code...

# ...existing code...

# Default personality prompt
DEFAULT_PERSONALITY = """You are a friendly and helpful AI assistant. Please respond in a warm, 
conversational manner while being helpful and informative. Feel free to use friendly phrases but do not overdo it, but keep the responses concise and focused. If you don't know something, be honest about it in a friendly way."""

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    user_message = data.get('message')
    chat_id = data.get('chat_id')
    is_new_chat = data.get('is_new_chat', False)

    if not chat_id or not user_message:
        return jsonify({"error": "Chat ID and message are required"}), 400

    try:
        db = get_db()
        user = db.execute('SELECT id FROM users WHERE username = ?', 
                         (session['username'],)).fetchone()
        
        # Get relevant documents only for this chat
        documents = db.execute('''
            SELECT d.content 
            FROM documents d 
            JOIN messages m ON m.chat_id = ? 
            WHERE d.user_id = ? 
            AND m.content LIKE 'PDF uploaded:%'
        ''', (chat_id, user['id'])).fetchall()
        
        # Create document context
        doc_context = ""
        if documents:
            doc_context = "\nAvailable documents:\n"
            for doc in documents:
                doc_context += doc['content'][:1000] + "...\n"
        
        # Get chat messages only if not a new chat
        previous_messages = []
        if not is_new_chat:
            previous_messages = db.execute('''
                SELECT role, content 
                FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp''', (chat_id,)).fetchall()
        
        # Save user message
        db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                   (chat_id, 'user', user_message, datetime.now().isoformat()))
        db.commit()

        context = DEFAULT_PERSONALITY + doc_context
        if not is_new_chat:
            context += "\n\nPrevious conversation:\n"
            context += "\n".join([f"{'User' if msg['role']=='user' else 'Assistant'}: {msg['content']}" 
                                for msg in previous_messages])
        context += f"\nUser: {user_message}\nAssistant: "

        # Generate response
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(context)
        bot_response = response.text.replace('Assistant:', '').strip()

        # Save bot response
        db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                   (chat_id, 'assistant', bot_response, datetime.now().isoformat()))
        db.commit()
        db.close()
        
        return jsonify({"response": bot_response})
    except Exception as e:
        print(f"Error in send_message: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
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
    
    
# UPLOADING DOCUMENTS
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_pdf', methods=['POST'])
@login_required
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        try:
            # Read PDF content
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            content = ""
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"

            # Save to database
            db = get_db()
            user = db.execute('SELECT id FROM users WHERE username = ?', 
                            (session['username'],)).fetchone()
            
            # Store in documents table
            db.execute('INSERT INTO documents (filename, content, upload_date, user_id) VALUES (?, ?, ?, ?)',
                      (secure_filename(file.filename), content, datetime.now().isoformat(), user['id']))
            db.commit()
            
            # Add to current chat context
            if 'current_chat_id' in session:
                db.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                          (session['current_chat_id'], 'system', f"PDF Content from {file.filename}: {content[:1000]}...", 
                           datetime.now().isoformat()))
                db.commit()
            
            db.close()
            return jsonify({"success": True, "message": "File uploaded and processed successfully"})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Invalid file type"}), 400


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)