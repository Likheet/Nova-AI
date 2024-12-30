import secrets
from dotenv import load_dotenv, set_key
import os

def generate_secret_key():
    # Generate a secure secret key
    secret_key = secrets.token_hex(32)
    
    # Get the absolute path to .env
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    # Load existing .env file
    load_dotenv(env_path)
    
    # Set the new secret key
    set_key(env_path, 'SECRET_KEY', secret_key)
    
    print(f"Secret key generated and saved to .env file")

if __name__ == "__main__":
    generate_secret_key()