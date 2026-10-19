import base64
import hashlib
import hmac
import os
import time
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings

ROLES = {"viewer": 0, "analyst": 1, "admin": 2}
COOKIE = "ep_session"


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def make_token(email: str, role: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": email, "role": role, "iat": now, "exp": now + get_settings().jwt_ttl_hours * 3600},
                      get_settings().secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def claims_from_request(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE)
    return decode_token(token) if token else None


async def current_user(request: Request) -> dict[str, Any]:
    claims = claims_from_request(request)
    if not claims:
        raise HTTPException(401, "login required")
    return claims


def require_role(min_role: str):
    async def dep(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if ROLES.get(user.get("role", ""), -1) < ROLES[min_role]:
            raise HTTPException(403, f"{min_role} role required")
        return user

    return dep
