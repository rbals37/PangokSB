from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = 'yihyunjinbyoungsin'  # 실제 프로덕션에서는 환경 변수로 관리해야 합니다

# FastAPI 백엔드 URL
API_URL = "http://localhost:8000"

@app.template_filter('md5')
def md5_filter(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        response = requests.post(
            f"{API_URL}/token",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            session['access_token'] = token_data['access_token']
            session['username'] = username  # 사용자 이름을 세션에 저장
            flash('로그인 성공!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('로그인 실패. 사용자 이름 또는 비밀번호를 확인하세요.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_data = {
            "username": username,
            "password": password,
        }
        
        response = requests.post(
            f"{API_URL}/register",
            json=user_data
        )
        
        if response.status_code == 200:
            flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
            return redirect(url_for('login'))
        else:
            error_data = response.json()
            flash(f'회원가입 실패: {error_data.get("detail", "알 수 없는 오류")}', 'error')
    
    return render_template('register.html')

@app.route('/profile')
@login_required
def profile():
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    response = requests.get(f"{API_URL}/users/me", headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        return render_template('profile.html', user=user_data)
    else:
        session.pop('access_token', None)
        session.pop('username', None)  # 사용자 이름도 세션에서 제거
        flash('세션이 만료되었습니다. 다시 로그인해주세요.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('access_token', None)
    session.pop('username', None)  # 사용자 이름도 세션에서 제거
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/room/<room_id>')
def room(room_id):
    if room_id not in ['A', 'B', 'C']:
        flash('존재하지 않는 방입니다.', 'error')
        return redirect(url_for('index'))
    
    return render_template('room.html', room_id=room_id)

@app.route('/verify-password', methods=['POST'])
@login_required
def verify_password():
    password = request.json.get('password')
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    response = requests.post(f"{API_URL}/verify-password", json={"password": password}, headers=headers)
    
    if response.status_code == 200:
        return response.json(), response.status_code
    else:
        error_data = response.json()
        return {"error": error_data.get("detail", "비밀번호 확인에 실패했습니다.")}, response.status_code

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    profile_data = request.json
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    response = requests.post(f"{API_URL}/update-profile", json=profile_data, headers=headers)
    
    if response.status_code == 200:
        flash('프로필이 성공적으로 업데이트되었습니다.', 'success')
        return response.json(), response.status_code
    else:
        error_data = response.json()
        flash(f'프로필 업데이트 실패: {error_data.get("detail", "알 수 없는 오류")}', 'error')
        return {"error": error_data.get("detail", "프로필 업데이트에 실패했습니다.")}, response.status_code

if __name__ == '__main__':
    app.run(debug=True) 