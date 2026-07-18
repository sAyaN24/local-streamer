"""Password hashing and app-level session tokens for user auth.

Deliberately separate from common/tokens.py: these JWTs are signed with
settings.auth_jwt_secret and are only ever verified by this API's own
get_current_user dependency -- livekit-server never sees them, and LiveKit's
viewer/publisher tokens (common/tokens.py) are never accepted here. Two
different trust domains, two different secrets.
"""

import time
from typing import Any

import bcrypt
import jwt

from streammark.common.config import Settings


class InvalidSessionTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def mint_session_token(settings: Settings, user_id: str, email: str) -> tuple[str, int]:
    ttl_seconds = int(settings.auth_token_ttl.total_seconds())
    now = int(time.time())
    payload = {"sub": user_id, "email": email, "iat": now, "exp": now + ttl_seconds}
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")
    return token, ttl_seconds


def decode_session_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidSessionTokenError(str(exc)) from exc
