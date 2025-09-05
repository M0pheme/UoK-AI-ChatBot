from flask import Flask, render_template, request, jsonify, session, make_response
import sqlite3
import json
import random
import re
import os
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')





def init_db():
    conn = sqlite3.connect('chatpy.db')
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        international TEXT,
        student_category TEXT,
        student_type TEXT,
        grade TEXT,
        province TEXT,
        school_name TEXT,
        student_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )''')

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect('chatpy.db')
    conn.row_factory = sqlite3.Row
    return conn


def insert_message(session_id, sender, content):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO messages (session_id, sender, content) VALUES (?, ?, ?)',
              (session_id, sender, content))
    conn.commit()
    conn.close()

def count_session_messages(session_id, sender='user'):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM messages WHERE session_id = ? AND sender = ?',
              (session_id, sender))
    count = c.fetchone()[0]
    conn.close()
    return count

# Load intents
def load_intents():
    try:
        with open('intents.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"intents": []}


def bot_reply(text):
    intents = load_intents()
    text_lower = text.lower()

    # Find matching intent
    for intent in intents.get('intents', []):
        for pattern in intent.get('patterns', []):
            if re.search(pattern.lower(), text_lower):
                return random.choice(intent.get('responses', ['I understand.']))

    # Fallback response
    fallback_responses = [
        "I'm not sure about that. Can you try asking about applications, fees, or general university information?",
        "I didn't quite understand. Would you like to know about university applications or student fees?",
        "Could you rephrase that? I can help with information about university applications, fees, and general inquiries."
    ]
    return random.choice(fallback_responses)


# Routes
@app.route('/')
def index():
    return render_template('chatbot.html')  # Now serves the chat widget directly


@app.route('/chat')
def chat():
    return render_template('chatbot.html')


@app.route('/api/save_user', methods=['POST'])
def save_user():
    try:
        data = request.get_json()

        # Insert user data
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO users (full_name, email, international, student_category,
                                        student_type, grade, province, school_name, student_number)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data.get('full_name'), data.get('email'), data.get('international'),
                   data.get('student_category'), data.get('student_type'), data.get('grade'),
                   data.get('province'), data.get('school_name'), data.get('student_number')))

        user_id = c.lastrowid

        # Create session
        session_id = str(uuid.uuid4())
        c.execute('INSERT INTO sessions (session_id, user_id) VALUES (?, ?)',
                  (session_id, user_id))

        conn.commit()
        conn.close()

        # Set session cookie
        response = make_response(jsonify({'success': True, 'session_id': session_id}))
        response.set_cookie('chatpy_session', session_id, max_age=86400)  # 24 hours

        return response

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        session_id = data.get('session_id') or request.cookies.get('chatpy_session')
        user_message = data.get('message', '').strip()

        if not session_id or not user_message:
            return jsonify({'success': False, 'error': 'Missing session_id or message'}), 400

        # Check message limit (10 user messages per session)
        user_sent = count_session_messages(session_id, 'user')
        if user_sent >= 10:
            return jsonify({
                'success': False,
                'error': 'limit_reached',
                'message': 'You have reached the maximum of 10 messages for this session.'
            })

        # Save user message
        insert_message(session_id, 'user', user_message)

        # Generate bot response
        bot_response = bot_reply(user_message)

        # Check if this will be the 10th user message after saving
        user_sent_after = count_session_messages(session_id, 'user')
        if user_sent_after >= 10:
            bot_response += "\n\nThis was your 10th message. This session has now ended. Thank you for using ChatPy!"

        # Save bot message
        insert_message(session_id, 'bot', bot_response)

        return jsonify({
            'success': True,
            'response': bot_response,
            'messages_left': max(0, 10 - user_sent_after),
            'session_ended': user_sent_after >= 10
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

init_db()
if __name__ == '__main__':

    app.run(debug=True)