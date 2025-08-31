from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import sqlite3
import os
from utils import get_response, predict_class

app = Flask(__name__, template_folder='templates')
app.secret_key = "supersecretkey"

# Ensure database directory exists
os.makedirs("database", exist_ok=True)
DB_PATH = os.path.join("database", "bot.db")


# ------------------- Routes -------------------

# Home / Default page
@app.route('/')
def index():
    return render_template('UOF.html')
# Default login/registration Page
def default():
    return render_template('Default.html')
# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Authenticate user here
        flash("Logged in successfully", "success")
        return redirect(url_for('index'))
    return render_template('Login.html')




# Registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('Register.html')


# UOF page
@app.route('/UOF')
def uof():
    return render_template('UOF.html')

# Booking & Consultations page
@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        # You can handle form submission here
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        classification = request.form.get('classification')
        service = request.form.get('service')
        slot = request.form.get('slot')
        # Save to database or text file here
        flash('Booking submitted successfully!', 'success')
        return redirect(url_for('booking'))
    return render_template('Booking.html')

# Faculties page
@app.route('/faculties')
def faculties():
    return render_template('Faculties.html')

# Delete Notices page
@app.route('/delete_notices')
def delete_notices():
    return render_template('Notices.html')

# Profile / Update Details page
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        # Handle profile update form submission
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('Profile.html')

# Chatbot message handler
@app.route('/handle_message', methods=['POST'])
def handle_message():
    message = request.json['message']
    intents_list = predict_class(message)
    response = get_response(intents_list)
    return jsonify({'response': response})

# Logout route (redirects to home)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('default'))

# curl -X POST http://127.0.0.1:5000/handle_message -d '{"message":"what is coding"}' -H "Content-Type: application/json"


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
    print(os.path.exists("templates/chatbot.html"))
