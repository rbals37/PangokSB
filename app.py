# c:\Users\USER\Desktop\Project\PGSB\app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "pangok is best jot hight school"#os.urandom(24)  # Set a secret key for sessions


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
        room_id INTEGER NOT NULL,
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

    # Create report table (신고)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id TEXT,
        target_id TEXT,
        target_name TEXT,
        content TEXT NOT NULL,
        report_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create aircon vote table (에어컨 투표)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aircon_votes (
        vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        vote TEXT NOT NULL, -- 'on' 또는 'off'
        vote_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    # Create study timer table (과목별 공부 시간)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_times (
        time_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        start_time DATETIME,
        end_time DATETIME,
        duration INTEGER DEFAULT 0, -- 초 단위 누적 시간
        FOREIGN KEY (user_id) REFERENCES users(user_id)
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
    return redirect(url_for('check'))     # Redirect to login by default


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
            return render_template('login.html', error='잘못된 학번 또는 비밀번호입니다.')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('signup.html', error='비밀번호가 일치하지 않습니다.')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (student_id, password) VALUES (?, ?)", (student_id, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))  # Redirect to login after successful signup
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('signup.html', error='학번이 이미 존재합니다.')

    return render_template('signup.html')

@app.route('/check')
def check():
    room_id = request.args.get('room_id', type=int)  # 기본값은 1번 자습실
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seats WHERE room_id = ?", (room_id,))
    seats = cursor.fetchall()
    conn.close()
    return render_template('check.html', seats=seats, room_id=room_id)


@app.route('/reserve', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    seat_id = request.form.get('seat_id')
    if not seat_id:
        return redirect(url_for('check'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # 현재 좌석의 자습실 번호 확인
    cursor.execute("SELECT room_id FROM seats WHERE seat_id = ?", (seat_id,))
    current_room = cursor.fetchone()
    room_id = current_room['room_id'] if current_room else 1

    # 기존 예약이 있는지 확인
    cursor.execute("SELECT seat_id FROM reservations WHERE user_id = ?", (user_id,))
    old_reservation = cursor.fetchone()
    if old_reservation:
        # 기존 좌석을 사용 가능하게 변경
        cursor.execute("UPDATE seats SET is_available = TRUE WHERE seat_id = ?", (old_reservation['seat_id'],))
        # 기존 예약 삭제
        cursor.execute("DELETE FROM reservations WHERE user_id = ?", (user_id,))

    # 좌석 사용 가능 여부 확인
    cursor.execute("SELECT is_available FROM seats WHERE seat_id = ?", (seat_id,))
    seat = cursor.fetchone()
    if not seat or not seat['is_available']:
        conn.close()
        return redirect(url_for('check', room_id=room_id))

    # 좌석 예약
    try:
        cursor.execute("INSERT INTO reservations (user_id, seat_id) VALUES (?, ?)", (user_id, seat_id))
        cursor.execute("UPDATE seats SET is_available = FALSE WHERE seat_id = ?", (seat_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('check', room_id=room_id))
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error during reservation: {e}")
        return redirect(url_for('check', room_id=room_id))


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
    SELECT seats.room_id, seats.row, seats.col
    FROM reservations
    JOIN seats ON reservations.seat_id = seats.seat_id
    WHERE reservations.user_id = ?
    """, (user_id,))
    reservations = cursor.fetchall()

    conn.close()
    return render_template('info.html', user=user, reservations=reservations)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user is None:
        return redirect(url_for('login'))
    if user['user_id'] != 1:
        return "You are not authorized to view this page"
    return render_template('admin_panel.html')


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
        conn = get_db_connection()
        cursor = conn.cursor()

        # Clear existing seats
        cursor.execute("DELETE FROM seats")

        # Create new seats for each room
        # 자습실 1, 2는 6x6
        for room_id in range(1, 3):
            for row in range(1, 7):
                for col in range(1, 7):
                    cursor.execute("INSERT INTO seats (row, col, room_id) VALUES (?, ?, ?)", (row, col, room_id))
        
        # 자습실 3은 5x6
        for row in range(1, 6):
            for col in range(1, 7):
                cursor.execute("INSERT INTO seats (row, col, room_id) VALUES (?, ?, ?)", (row, col, 3))

        conn.commit()
        conn.close()

    return render_template('arrange.html')  # Create or modify the seat arrangement


@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session or session['user_id'] != 1:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY report_time DESC")
    reports = cursor.fetchall()
    conn.close()
    return render_template('reports.html', reports=reports)


# --- 열품타 시스템 API ---

@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    reporter_id = data.get('reporter_id')
    target_id = data.get('target_id')
    target_name = data.get('target_name')
    content = data.get('content')
    if not content:
        return jsonify({'success': False, 'message': '내용은 필수입니다.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reports (reporter_id, target_id, target_name, content) VALUES (?, ?, ?, ?)", (reporter_id, target_id, target_name, content))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '신고가 접수되었습니다.'})

@app.route('/vote_aircon', methods=['POST'])
def vote_aircon():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    data = request.get_json()
    vote = data.get('vote')  # 'on' 또는 'off'
    if vote not in ['on', 'off']:
        return jsonify({'success': False, 'message': '잘못된 투표 값입니다.'}), 400
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO aircon_votes (user_id, vote) VALUES (?, ?)", (user_id, vote))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '투표가 완료되었습니다.'})

@app.route('/study_timer', methods=['POST'])
def study_timer():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    data = request.get_json()
    subject = data.get('subject')
    action = data.get('action')  # 'start', 'stop', 'get'
    user_id = session['user_id']
    # 실제 타이머 로직은 추후 구현
    return jsonify({'success': True, 'message': '타이머 API 호출됨', 'subject': subject, 'action': action})

@app.route('/yeolpumta')
def yeolpumta():
    return render_template('yeolpumta.html')

@app.route('/info_json')
def info_json():
    if 'user_id' not in session:
        return jsonify({'error': 'not_logged_in'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'not_found'}), 404
    # 이름 필드가 없으므로 student_id만 반환
    return jsonify({'student_id': user['student_id'], 'name': user['student_id']})

if __name__ == '__main__':
    app.run(debug=True)