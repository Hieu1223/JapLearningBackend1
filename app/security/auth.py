import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from uuid import UUID
import bcrypt
from typing import Annotated, Optional
import secrets
import uuid

SECRET_KEY = "AAAAAA"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False

def create_access_token(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: UUID) -> str:
    return secrets.token_urlsafe(32)

def verify_refresh_token(session, token: str) -> Optional[UUID]:
    from ..database.security.queries import get_refresh_token
    refresh_token = get_refresh_token(session, token)
    if not refresh_token:
        return None
    if refresh_token.revoked:
        return None
    if refresh_token.expires_at < datetime.now(timezone.utc):
        return None
    return refresh_token.user_id

def get_current_user(token: str = Depends(oauth2_scheme)) -> UUID:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return UUID(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Session")

CurrentUser = Annotated[UUID, Depends(get_current_user)]