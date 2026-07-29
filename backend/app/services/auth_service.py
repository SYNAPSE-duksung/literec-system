import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken, User
from app.security import (
    create_refresh_token_value,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def signup(db: Session, *, email: str, password: str, name: str) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일입니다.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.")
    return user


def issue_refresh_token(db: Session, user_id: uuid.UUID) -> str:
    raw_token = create_refresh_token_value()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    return raw_token


def verify_refresh_token(db: Session, raw_token: str) -> User:
    token_hash = hash_refresh_token(raw_token)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
        .first()
    )
    if record is None or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "리프레시 토큰이 유효하지 않습니다.")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없습니다.")
    return user


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if record is not None:
        record.revoked = True
        db.commit()
