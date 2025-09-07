import os, uuid, re
from flask import Flask, render_template, request, jsonify, session, make_response, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from utils import (
    get_db, init_db,
    role_required, admin_required, login_required,
    bot_reply, load_intents,
    create_employee, create_student
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'SUPER SECRET KEY')

# Initialize DB (creates tables if missing)
init_db()

# -----------------------------
# Helper functions (message ops)
# -----------------------------
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

# -----------------------------
# Routes - UI
# -----------------------------
@app.route('/')
def index():
    return render_template('chatbot.html')

@app.route('/chat')
def chat():
    return render_template('chatbot.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))

# -----------------------------
# Login Route (admin / employee / student)
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()

        # Try to fetch user from admin, employees, or students
        cursor.execute("""
            SELECT id, fname, lname, email, 'admin' as role, password FROM admin WHERE email=?
            UNION
            SELECT id, fname, lname, email, role, password FROM employees WHERE email=?
            UNION
            SELECT id, fname, lname, email, role, password FROM students WHERE email=?
        """, (username, username, username))

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # Store session
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['full_name'] = f"{user['fname']} {user['lname']}"

            # Redirect based on role
            if session['user_role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif session['user_role'] == 'employee':
                return redirect(url_for('employee_dashboard'))
            elif session['user_role'] == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                flash("Unknown role", "danger")
                return redirect(url_for('login'))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for('login'))

    return render_template("Login.html")

# -----------------------------
# Role-protected dashboards
# -----------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("Admin.html", user=session)

@app.route('/employee')
@role_required('employee')
def employee_dashboard():
    user_id = session.get('user_id')
    conn = get_db()
    user = conn.execute("SELECT * FROM employees WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return render_template("Employees.html", user=user)

@app.route('/student')
@login_required
def student_dashboard():
    db = get_db()
    user_id = session.get('user_id')

    if not user_id:
        flash("Please login to access your dashboard.")
        return redirect(url_for('login'))

    student = db.execute("SELECT * FROM students WHERE id = ?", (user_id,)).fetchone()
    if not student:
        flash("Student not found.")
        return redirect(url_for('login'))

    # Fetch bookings matching student's name
    bookings = db.execute(
        "SELECT * FROM bookings WHERE fname = ? AND lname = ? ORDER BY slot ASC", (student['fname'], student['lname'])
    ).fetchall()

    notices = db.execute("SELECT * FROM notices ORDER BY created_at DESC").fetchall()
    db.close()

    return render_template("Students.html", user=student, bookings=bookings, notices=notices)

# Update profile (student or employee)
@app.route('/update_profile', methods=['POST'])
@role_required('student', 'employee')
def update_profile():
    user_id = session.get('user_id')
    user_role = session.get('user_role')

    fname = request.form.get('fname', '').strip()
    lname = request.form.get('lname', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if password and password != confirm_password:
        flash("Passwords do not match", "danger")
        return redirect(url_for('student_dashboard') if user_role == 'student' else url_for('employee_dashboard'))

    conn = get_db()
    c = conn.cursor()

    table = 'students' if user_role == 'student' else 'employees'
    params = [fname, lname, email]

    query = f"UPDATE {table} SET fname=?, lname=?, email=?"
    if password:
        hashed_password = generate_password_hash(password)
        query += ", password=?"
        params.append(hashed_password)

    query += " WHERE id=?"
    params.append(user_id)

    c.execute(query, params)
    conn.commit()
    conn.close()

    session['full_name'] = f"{fname} {lname}"
    flash("Profile updated successfully!", "success")
    return redirect(url_for('student_dashboard') if user_role == 'student' else url_for('employee_dashboard'))

# -----------------------------
# API routes - Create / Read / Delete Employees & Students
# -----------------------------
@app.route('/api/employee', methods=['POST'])
@admin_required
def api_create_employee():
    data = request.get_json() or {}
    fname = (data.get('fname') or '').strip()
    lname = (data.get('lname') or '').strip()
    if not fname or not lname:
        return jsonify({'success': False, 'error': 'First and last name required'}), 400

    result = create_employee(fname, lname)
    return jsonify({'success': True, **result})

@app.route('/api/employee', methods=['GET'])
@admin_required
def api_get_employees():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM employees ORDER BY id ASC")
    employees = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(employees)

@app.route('/api/employee/<int:emp_id>', methods=['DELETE'])
@admin_required
def api_delete_employee(emp_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Student endpoints
@app.route('/api/student', methods=['POST'])
@admin_required
def api_create_student():
    data = request.get_json() or {}
    fname = (data.get('fname') or '').strip()
    lname = (data.get('lname') or '').strip()
    if not fname or not lname:
        return jsonify({'success': False, 'error': 'First and last name required'}), 400

    result = create_student(fname, lname)
    return jsonify({'success': True, **result})

@app.route('/api/student', methods=['GET'])
@admin_required
def api_get_student():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY id ASC")
    students = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(students)

@app.route('/api/student/<int:stu_id>', methods=['DELETE'])
@admin_required
def api_delete_student(stu_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM students WHERE id = ?", (stu_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -----------------------------
# API: Delete a message (admin)
# -----------------------------
@app.route('/api/message/<int:msg_id>', methods=['DELETE'])
@admin_required
def delete_message(msg_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -----------------------------
# Save user (public chatbot onboarding)
# -----------------------------
@app.route('/api/save_user', methods=['POST'])
def save_user():
    try:
        data = request.get_json() or {}
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (full_name, email, international, student_category,
                               student_type, grade, province, school_name, student_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data.get('full_name'), data.get('email'), data.get('international'),
                   data.get('student_category'), data.get('student_type'), data.get('grade'),
                   data.get('province'), data.get('school_name'), data.get('student_number')))
        user_id = c.lastrowid

        # Create session id and link
        session_id = str(uuid.uuid4())
        c.execute('INSERT INTO sessions (session_id, user_id) VALUES (?, ?)', (session_id, user_id))
        conn.commit()
        conn.close()

        response = make_response(jsonify({'success': True, 'session_id': session_id}))
        response.set_cookie('chatpy_session', session_id, max_age=86400)  # 1 day
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -----------------------------
# Send message (chat) endpoint
# -----------------------------
@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id') or request.cookies.get('chatpy_session')
        user_message = (data.get('message') or '').strip()

        if not session_id or not user_message:
            return jsonify({'success': False, 'error': 'Missing session_id or message'}), 400

        user_sent = count_session_messages(session_id, 'user')
        if user_sent >= 10:
            return jsonify({
                'success': False,
                'error': 'limit_reached',
                'message': 'You have reached the maximum of 10 messages for this session.'
            })

        insert_message(session_id, 'user', user_message)
        bot_response = bot_reply(user_message)

        user_sent_after = count_session_messages(session_id, 'user')
        if user_sent_after >= 10:
            bot_response += "\n\nThis was your 10th message. This session has now ended. Thank you for using ChatPy!"

        insert_message(session_id, 'bot', bot_response)

        return jsonify({
            'success': True,
            'response': bot_response,
            'messages_left': max(0, 10 - user_sent_after),
            'session_ended': user_sent_after >= 10
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -----------------------------
# Notices (view only)
# -----------------------------
@app.route('/notices')
@login_required
def view_notices():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT title, content, created_at FROM notices ORDER BY created_at DESC")
    notices = c.fetchall()
    conn.close()
    return render_template("Notices.html", notices=notices)

# -----------------------------
# Records page (Admin)
# -----------------------------
@app.route('/records', methods=['GET', 'POST'])
@admin_required
def records():
    messages = []
    bookings = []

    conn = get_db()
    c = conn.cursor()

    report_type = request.form.get('report_type') if request.method == 'POST' else 'booking'
    service_categories = request.form.getlist('service_category')
    sort_options = request.form.getlist('sort')

    # Fetch chatbot messages
    c.execute('''
        SELECT m.id, m.session_id, m.sender, m.content, m.timestamp, u.full_name
        FROM messages m
        LEFT JOIN sessions s ON m.session_id = s.session_id
        LEFT JOIN users u ON s.user_id = u.id
        ORDER BY m.timestamp DESC
    ''')
    messages = [dict(row) for row in c.fetchall()]

    # Build bookings query with filters
    query = "SELECT id, fname, lname, classification, service, slot, created_at FROM bookings"
    filters = []
    params = []

    if service_categories:
        placeholders = ",".join("?" for _ in service_categories)
        filters.append(f"service IN ({placeholders})")
        params.extend(service_categories)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    # Sorting
    if 'alphabetical' in sort_options:
        query += " ORDER BY fname ASC, lname ASC"
    elif 'date' in sort_options:
        query += " ORDER BY created_at DESC"
    else:
        query += " ORDER BY created_at DESC"

    c.execute(query, params)
    bookings = [dict(row) for row in c.fetchall()]

    conn.close()
    return render_template("Admin.html", messages=messages, bookings=bookings)

# -----------------------------
# Booking route (all roles)
# -----------------------------
@app.route('/booking', methods=['GET', 'POST'])
@role_required('admin', 'employee', 'student')
def booking():
    if request.method == 'POST':
        try:
            fname = request.form.get('fname')
            lname = request.form.get('lname')
            classification = request.form.get('classification')
            service = request.form.get('service')
            slot = request.form.get('slot')
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT INTO bookings (fname, lname, classification, service, slot) VALUES (?, ?, ?, ?, ?)',
                      (fname, lname, classification, service, slot))
            conn.commit()
            conn.close()
            return render_template("Booking.html", success=True)
        except Exception as e:
            return render_template("Booking.html", error=str(e))
    return render_template("Booking.html")

# Run app
if __name__ == '__main__':
    app.run(debug=True)
