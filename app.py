from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
API_KEY = os.getenv("PERPLEXITY_API_KEY")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    
    url = "https://api.perplexity.ai/chat/completions"
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "Be precise and concise."
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "search_domain_filter": ["perplexity.ai"],
        "return_images": False,
        "return_related_questions": False,
        "search_recency_filter": "month",
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        bot_response = response.json()["choices"][0]["message"]["content"]
        return jsonify({
            "response": bot_response,
            "citations": response.json().get("citations", [])  # Include citations if available
        })
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)