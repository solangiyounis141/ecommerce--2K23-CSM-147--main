import datetime as dt
import os

import bcrypt
import jwt
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .errors import AppError
from .models import User
from .schemas import LoginRequest

bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_token(user: User) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    return jwt.encode({"sub": str(user.id), "exp": exp}, _secret(), algorithm="HS256")


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(401, "not_authenticated", "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "invalid_token", "Invalid or expired token")
    if user is None:
        raise AppError(401, "invalid_token", "Invalid or expired token")
    if user.role != "admin":  # role is read from the DB, never trusted from the token
        raise AppError(403, "forbidden", "Administrator role required")
    return user


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise AppError(401, "invalid_credentials", "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer"}
