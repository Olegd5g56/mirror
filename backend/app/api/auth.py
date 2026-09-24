from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import COOKIE_NAME, CurrentUser, DbSession
from app.config import settings
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserOut
from app.services.security import JWTDecodeError, decode_jwt, issue_jwt, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, session: DbSession) -> LoginResponse:
    res = await session.execute(select(User).where(User.username == body.username))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний логін або пароль",
        )
    token = issue_jwt(user.id)
    _set_auth_cookie(response, token)
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(
    response: Response,
    user: CurrentUser,
    cookie_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> UserOut:
    if not cookie_token:
        _set_auth_cookie(response, issue_jwt(user.id))
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, user: CurrentUser) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return None


@router.get("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify(
    cookie_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> None:
    """Internal: nginx auth_request для /media/thumbs і /media/posters."""
    if not cookie_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    try:
        decode_jwt(cookie_token)
    except JWTDecodeError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED) from e
