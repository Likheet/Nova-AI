import sqlite3
from datetime import datetime

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

def save_chat(chat_id, title):
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('INSERT INTO chats (id, title, created_at) VALUES (?, ?, ?)',
              (chat_id, title, datetime.now()))
    conn.commit()
    conn.close()

def save_message(chat_id, role, content):
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
              (chat_id, role, content, datetime.now()))
    conn.commit()
    conn.close()

def get_chat_history():
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('SELECT id, title, created_at FROM chats ORDER BY created_at DESC')
    chats = c.fetchall()
    conn.close()
    return chats

def get_chat_messages(chat_id):
    conn = sqlite3.connect('chats.db')
    c = conn.cursor()
    c.execute('SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp',
              (chat_id,))
    messages = c.fetchall()
    conn.close()
    return messages