# create_tables.py
import sqlite3

def create_tables():
    try:
        conn = sqlite3.connect('chats.db')
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT UNIQUE NOT NULL,
             password TEXT NOT NULL,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        
        # Update chats table to include user_id
        c.execute('''
            CREATE TABLE IF NOT EXISTS chats
            (id TEXT PRIMARY KEY,
             title TEXT,
             created_at TIMESTAMP,
             user_id INTEGER,
             FOREIGN KEY (user_id) REFERENCES users (id))
        ''')
        
        conn.commit()
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_tables()