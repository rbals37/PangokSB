# c:\Users\USER\Desktop\Project\PGSB\app.py
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for sessions


# Database Configuration (SQLite)
DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # Create seats table (Example - Adjust as needed)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seats (
        seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        row INTEGER NOT NULL,
        col INTEGER NOT NULL,
        is_available BOOLEAN DEFAULT TRUE
    )
    """)

    # Create reservations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        seat_id INTEGER NOT NULL,
        reservation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (seat_id) REFERENCES seats(seat_id)
    )
    """)
    conn.commit()
    conn.close()


# Initialize the database
with app.app_context():
    init_db()

# --- Routes ---

@app.route('/')
def index():
    return render_template('login.html')  # Redirect to login by default


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE student_id = ? AND password = ?", (student_id, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['user_id']
            return redirect(url_for('check')) # Redirect to check after successful login
        else:
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (student_id, password) VALUES (?, ?)", (student_id, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))  # Redirect to login after successful signup
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('signup.html', error='Student ID already exists')

    return render_template('signup.html')

@app.route('/check')
def check():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seats")
    seats = cursor.fetchall()
    conn.close()
    return render_template('check.html', seats=seats)


@app.route('/reserve', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    seat_id = request.form.get('seat_id')
    if not seat_id:
        return redirect(url_for('check')) # Or handle the error appropriately

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the seat is available
    cursor.execute("SELECT is_available FROM seats WHERE seat_id = ?", (seat_id,))
    seat = cursor.fetchone()
    if not seat or not seat['is_available']:
        conn.close()
        # Handle the error (e.g., seat already taken)
        return redirect(url_for('check'))

    # Reserve the seat
    try:
        cursor.execute("INSERT INTO reservations (user_id, seat_id) VALUES (?, ?)", (user_id, seat_id))
        cursor.execute("UPDATE seats SET is_available = FALSE WHERE seat_id = ?", (seat_id,))
        conn.commit()
        conn.close()
        # Redirect back to check
        return redirect(url_for('check'))
    except Exception as e:
        conn.rollback()
        conn.close()
        # Handle the error (e.g., database error)
        print(f"Error during reservation: {e}")
        return redirect(url_for('check'))


@app.route('/info')
def info():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    cursor.execute("""
    SELECT seats.row, seats.col
    FROM reservations
    JOIN seats ON reservations.seat_id = seats.seat_id
    WHERE reservations.user_id = ?
    """, (user_id,))
    reservations = cursor.fetchall() # Get reservations

    conn.close()
    return render_template('info.html', user=user, reservations=reservations) # Pass reservations to the template


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # In a real application, you'd check if the user is an admin
    # For this example, we will hard code the admin user_id
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return redirect(url_for('login')) # Or handle the error

    # Check if the user is an admin.
    if user['user_id'] != 1:  # Assuming user_id 1 is the admin
        return "You are not authorized to view this page"

    return render_template('admin.html')


@app.route('/admin/arrange', methods=['GET', 'POST'])
def arrange():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return redirect(url_for('login')) # Or handle the error

    # Check if the user is an admin.
    if user['user_id'] != 1:  # Assuming user_id 1 is the admin
        return "You are not authorized to view this page"

    if request.method == 'POST':
        rows = int(request.form.get('rows', 10))  # Default to 10 rows
        cols = int(request.form.get('cols', 10))  # Default to 10 columns

        conn = get_db_connection()
        cursor = conn.cursor()

        # Clear existing seats
        cursor.execute("DELETE FROM seats")

        # Create new seats
        for row in range(1, rows + 1):
            for col in range(1, cols + 1):
                cursor.execute("INSERT INTO seats (row, col) VALUES (?, ?)", (row, col))
        conn.commit()
        conn.close()

    return render_template('arrange.html')  # Create or modify the seat arrangement


if __name__ == '__main__':
    app.run(debug=True)