# create_tables.py
import sqlite3

def create_tables():
    try:
        conn = sqlite3.connect('chats.db')
        c = conn.cursor()
        
        # Create chats table
        c.execute('''
            CREATE TABLE IF NOT EXISTS chats
            (id TEXT PRIMARY KEY,
             title TEXT,
             created_at TIMESTAMP)
        ''')
        
        # Create messages table
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
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_tables()