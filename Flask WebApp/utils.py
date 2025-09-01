import os

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
    Example: @role_required("admin"), or @role_required("faculty", "admin")
    """
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session or "role" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))
            if session["role"] not in roles:
                flash("Access denied.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper
# -------------------------------
# Database initialization (optional helper)
# -------------------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()
    # Users table (roles: admin, staff, student)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','staff','student')),
            job_title TEXT
        )
    ''')
    # Queries table (for chatbot + contact forms)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    # Bookings table (for staff reports, optional)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            booking_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    # Notices table (CRUD by admin/staff)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


#=============================================
# ChatBot AI Handling
#=============================================
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
