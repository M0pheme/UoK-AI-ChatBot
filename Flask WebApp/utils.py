import os
import re

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import sqlite3
from functools import wraps
from flask import session, redirect, url_for, flash

import random
import json
import pickle
import numpy as np

import nltk
from nltk.stem import WordNetLemmatizer

from tensorflow.keras.models import load_model

from werkzeug.security import generate_password_hash

DB_NAME = "UoK.db"

#---------------------------------------------
# Database helper
#---------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --------------------------------------------
# Role-based access control
# ----------------------------------------------
def role_required(*roles):
    """
    Restrict access to users with one of the given roles.
    Example: @role_required("admin"), or @role_required("employee","admin")
    """
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session or "user_role" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))
            if session["user_role"] not in roles:
                flash("Access denied.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

def login_required(f):
    """Simple login-required decorator (any logged-in user)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------
# Admin Login Decorator
# ---------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash("Admin access required", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------
# Database initialization
# -------------------------------
def init_db():
    conn = get_db()
    c = conn.cursor()

    # Login table (legacy / optional)
    c.execute('''CREATE TABLE IF NOT EXISTS login (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','employee','student')),
        job_title TEXT
    )''')

    # Users table (for chatbot sessions linking)
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

    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Bookings table
    # Note: no student_id column here — bookings are recorded by names
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT NOT NULL,
        lname TEXT NOT NULL,
        classification TEXT NOT NULL,
        service TEXT NOT NULL,
        slot TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Notices table
    c.execute('''CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Admin table
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT NOT NULL,
        lname TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # Employees table (replacing staff)
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT NOT NULL,
        lname TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role='employee'),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         fname TEXT NOT NULL,
         lname TEXT NOT NULL,
         email TEXT UNIQUE NOT NULL,
         password TEXT NOT NULL,
         role TEXT NOT NULL CHECK(role='student'),
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Insert default admin (if not exists)
    admin_fname = "Admin"
    admin_lname = "User"
    admin_email = "admin-user@UoK.ac.za"
    admin_password = "admin@user"
    hashed_password = generate_password_hash(admin_password)

    c.execute("""INSERT OR IGNORE INTO admin (fname, lname, email, password)
                 VALUES (?, ?, ?, ?)""",
              (admin_fname, admin_lname, admin_email, hashed_password))

    conn.commit()
    conn.close()

#---------------------------------------------
# Auto-generate email and password
#---------------------------------------------
def create_employee(fname, lname):
    conn = get_db()
    c = conn.cursor()
    role = 'employee'

    # Insert employee to get id
    c.execute("INSERT INTO employees (fname, lname, email, password, role) VALUES (?, ?, ?, ?, ?)",
              (fname, lname, '', '', role))
    user_id = c.lastrowid

    # Auto-generate email & password (plain to share with admin)
    email = f"{user_id}-{lname}@UoK.ac.za"
    password = f"{user_id}@{lname}"

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Update record with generated credentials
    c.execute("UPDATE employees SET email = ?, password = ? WHERE id = ?",
              (email, hashed_password, user_id))
    conn.commit()
    conn.close()

    return {'id': user_id, 'email': email, 'password': password}

def create_student(fname, lname):
    conn = get_db()
    c = conn.cursor()
    role = 'student'

    # Insert student to get id
    c.execute("INSERT INTO students (fname, lname, email, password, role) VALUES (?, ?, ?, ?, ?)",
              (fname, lname, '', '', role))
    user_id = c.lastrowid

    # Auto-generate email & password
    email = f"{user_id}-{lname}@UoK.ac.za"
    password = f"{user_id}@{lname}"
    hashed_password = generate_password_hash(password)

    # Update record
    c.execute("UPDATE students SET email = ?, password = ? WHERE id = ?",
              (email, hashed_password, user_id))
    conn.commit()
    conn.close()

    return {'id': user_id, 'email': email, 'password': password}

#=============================================
# ChatBot AI Handling
#=============================================
def load_intents():
    try:
        with open('model/intents.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"intents": []}

def bot_reply(text):
    intents = load_intents()
    text_lower = text.lower()

    for intent in intents.get('intents', []):
        for pattern in intent.get('patterns', []):
            # use regex search for flexible matching
            if re.search(pattern.lower(), text_lower):
                return random.choice(intent.get('responses', ['I understand.']))

    # Fallback responses
    fallback_responses = [
        "I'm not sure about that. Can you try asking about applications, fees, or general university information?",
        "I didn't quite understand. Would you like to know about university applications or student fees?",
        "Could you rephrase that? I can help with information about university applications, fees, and general inquiries."
    ]
    return random.choice(fallback_responses)

def clean_up_sentence(sentence):
    lemmatizer = WordNetLemmatizer()
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word) for word in sentence_words]
    return sentence_words

def bag_of_words(sentence):
    words = pickle.load(open('model/words.pkl', 'rb'))
    sentence_words = clean_up_sentence(sentence)
    bag = [0] * len(words)
    for w in sentence_words:
        for i, word in enumerate(words):
            if word == w:
                bag[i] = 1
    return np.array(bag)

def predict_class(sentence):
    classes = pickle.load(open('model/classes.pkl', 'rb'))
    model = load_model('model/chatbot_model.keras')

    bow = bag_of_words(sentence)
    res = model.predict(np.array([bow]))[0]
    ERROR_THRESHOLD = 0.25

    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    results.sort(key=lambda x: x[1], reverse=True)

    return_list = []
    for r in results:
        return_list.append({'intent': classes[r[0]], 'probability': str(r[1])})

    return return_list

def get_response(intents_list):
    intents_json = json.load(open('model/intents.json'))
    tag = intents_list[0]['intent']
    list_of_intents = intents_json['intents']
    for i in list_of_intents:
        if i['tag'] == tag:
            result = random.choice(i['responses'])
            break
    return result
