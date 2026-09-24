from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.security import JWTDecodeError, decode_jwt

_bearer = HTTPBearer(auto_error=False)
COOKIE_NAME = "mirror_token"


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cookie_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    if creds is not None:
        token = creds.credentials
    elif cookie_token:
        token = cookie_token
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не вказано токен авторизації",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_jwt(token)
    except JWTDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний або прострочений токен авторизації",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Користувача не знайдено",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
