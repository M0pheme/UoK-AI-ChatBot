from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import sqlite3
import os
from utils import get_response, predict_class

app = Flask(__name__, template_folder='templates')
app.secret_key = "supersecretkey"

#-------------------------------------------------------
# Public routes
#-------------------------------------------------------


# Home / Default page
@app.route('/')
def index():
    return render_template('UOF.html')

# Default login/registration Page
def default():
    return render_template('Default.html')

# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["username"] = user["username"]
            session["job_title"] = user["job_title"]
            flash(f"Welcome {username}!")
            return redirect(url_for("home"))
        else:
            flash("Invalid login.")
    return render_template("login.html")

# Logout and redirect to home page
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))

@appp.route("/notices-post")
def notices-post():
    return render_template("Notices-post.html")


#-----------------------------------------------------
# Admin routes
#-----------------------------------------------------
@app.route("/admin/notices")
@role_required("admin")
def notices_admin():
    return render_template("Notices.html")

@app.route("/admin/report")
@role_required("admin")
def report_admin("admin")
    return render_template("Report.html")

#------------------------------------------------------
# Staff routes
#------------------------------------------------------
@app.route("/staff/profile")
@role_required("staff")
def staff_profile():
    retrn render_template("Profile.html")

@app.route("/staff/notices")
@role_required("staff", "admin")
def notices_staff():
    return render_template("Notices.html")

@app.route("staff/report")
@role_required("staff", "admin")
def report_staff():
    # Filter booking/queries by staff's job_title
    jpb_title = session.get("job_title")
    return render_template("Report.html", job_title=job_title)


#---------------------------------------------------------
# Student routes
# ---------------------------------------------------------
@app.route("/student/profile")
@role_required("student")
def student_profile():
    return render_template("Profile.html")

@app.route("/student/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, 'student')",
                (username, password)
            )
            conn.commit()
            flash("Registration successful! You can now log in.")
            return redirect(url_for("login"))
        except:
            flash("Username already exists.")
        finally:
            conn.close()
    return render_template('Register.html')


# UOF page
@app.route('/UOF')
def uof():
    return render_template('UOF.html')

# Booking & Consultations page
@app.route('/student/booking', methods=['GET', 'POST'])
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


# curl -X POST http://127.0.0.1:5000/handle_message -d '{"message":"what is coding"}' -H "Content-Type: application/json"


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
    print(os.path.exists("templates/chatbot.html"))
