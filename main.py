from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import pymongo
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request

app = FastAPI()

from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 환경 변수 로드
load_dotenv()

# MongoDB 연결 설정
MONGO_USERNAME = os.getenv("MONGO_USERNAME", "")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_DB = os.getenv("MONGO_DB", "auth_system")

# MongoDB 연결 문자열 생성
if MONGO_USERNAME and MONGO_PASSWORD:
    MONGO_URI = f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"

# MongoDB 클라이언트 생성
try:
    print(f"Connecting to MongoDB with URI: {MONGO_URI}")
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # 연결 테스트
    mongo_client.server_info()
    mongo_db = mongo_client[MONGO_DB]
    print("MongoDB connection successful")
except pymongo.errors.ServerSelectionTimeoutError as e:
    print(f"Could not connect to MongoDB: {e}")
    # 개발 환경에서는 계속 진행
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise
    else:
        print("Running in development mode without MongoDB")
        mongo_db = None

# 보안 설정
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")  # 개발용 기본값
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용으로 모든 오리진 허용, 프로덕션에서는 제한하세요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(db, username: str):
    if db is None:  # MongoDB 연결이 없는 경우 처리
        return None
    
    user_dict = db.users.find_one({"username": username})
    if user_dict:
        # MongoDB의 _id 필드 제거 (Pydantic 모델과 호환되지 않음)
        user_dict.pop("_id", None)
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str):
    user = get_user(mongo_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(mongo_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/register", response_model=User)
async def register_user(user: UserCreate):
    if mongo_db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    
    # 사용자 이름 중복 확인
    existing_user = get_user(mongo_db, user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    user_dict = {
        "username": user.username,
        "hashed_password": hashed_password,
        "disabled": False
    }
    
    # MongoDB에 사용자 저장
    try:
        mongo_db.users.insert_one(user_dict)
    except Exception as e:
        print(f"Error inserting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
    
    return User(**user_dict)

@app.post("/verify-password")
async def verify_password_endpoint(password_data: dict, current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = get_user(mongo_db, current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not verify_password(password_data["password"], user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    return {"message": "Password verified"}

@app.post("/update-profile")
async def update_profile(profile_data: dict, current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = get_user(mongo_db, current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 업데이트할 데이터 준비
    update_data = {}
    
    # 학번이 변경된 경우
    if "username" in profile_data and profile_data["username"] != current_user.username:
        # 새 학번이 이미 존재하는지 확인
        existing_user = get_user(mongo_db, profile_data["username"])
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        update_data["username"] = profile_data["username"]
    
    # 비밀번호가 제공된 경우에만 업데이트
    if "password" in profile_data and profile_data["password"]:
        update_data["hashed_password"] = get_password_hash(profile_data["password"])
    
    # MongoDB에 업데이트
    try:
        mongo_db.users.update_one(
            {"username": current_user.username},
            {"$set": update_data}
        )
    except Exception as e:
        print(f"MongoDB update error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    
    return {"message": "Profile updated successfully"}

# 헬스 체크 엔드포인트 추가
@app.get("/health")
async def health_check():
    """
    서버 상태 확인용 엔드포인트
    """
    try:
        if mongo_db:
            # 간단한 쿼리로 DB 연결 테스트
            mongo_db.command('ping')
            db_status = "connected"
        else:
            db_status = "not connected"
            
        return {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }