from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import get_db, User
from pydantic import BaseModel

# =================== CẤU HÌNH ===================

# Thay đổi SECRET_KEY này thành một chuỗi bí mật mạnh, dài và random (tốt nhất lưu trong .env)
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Thời gian sống của token (có thể tăng lên 1440 phút = 1 ngày)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =================== SCHEMAS ===================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: str  # user id (UUID string)
    email: str


# =================== HÀM HỖ TRỢ ===================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra password người dùng nhập có khớp với hash lưu trong DB không"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password trước khi lưu vào database"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Tạo JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> User:
    """Dependency: Lấy thông tin user hiện tại từ JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(id=user_id, email=payload.get("email", ""))
    except JWTError:
        raise credentials_exception
    
    user = db.get(User, token_data.id)
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Dependency nâng cao: Đảm bảo user đang active (nếu bạn có trường is_active)"""
    # Nếu bạn thêm trường is_active vào User thì có thể check ở đây
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Tài khoản bị vô hiệu hóa")
    return current_user


# =================== HÀM ĐĂNG NHẬP ===================

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Kiểm tra email + password, trả về user nếu đúng"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user