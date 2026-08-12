from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas.auth import AccessTokenResponse, AuthResponse, LoginRequest, SignupRequest, UserOut
from app.security import create_access_token, get_current_user
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # 로컬 개발(HTTP) 기준 — 운영 배포 시 True로 전환 필요
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, name=user.name)


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.signup(db, email=payload.email, password=payload.password, name=payload.name)
    return _user_out(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    access_token = create_access_token(user.id)
    refresh_token = auth_service.issue_refresh_token(db, user.id)
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=_user_out(user))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: Request, db: Session = Depends(get_db)) -> AccessTokenResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "리프레시 토큰이 없습니다.")
    user = auth_service.verify_refresh_token(db, raw_token)
    access_token = create_access_token(user.id)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is not None:
        auth_service.revoke_refresh_token(db, raw_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)
