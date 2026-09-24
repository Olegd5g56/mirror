from datetime import datetime, timedelta, timezone
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from jose import JWTError, jwt

from app.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except VerificationError:
        return False
    return True


def issue_jwt(user_id: UUID) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class JWTDecodeError(Exception):
    pass


def decode_jwt(token: str, *, verify_exp: bool = True) -> UUID:
    """Повертає user_id з токена.

    `verify_exp=False` потрібен у pre-finish хука: заливка може тривати довше TTL.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": verify_exp},
        )
    except JWTError as e:
        raise JWTDecodeError(str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise JWTDecodeError("missing sub")
    try:
        return UUID(sub)
    except (ValueError, TypeError) as e:
        raise JWTDecodeError("sub not a uuid") from e
