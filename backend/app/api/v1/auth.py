from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import COOKIE, current_user, hash_password, make_token, require_role, verify_password
from app.core.config import get_settings
from app.core.security import rate_limit
from app.db.session import get_session
from app.models import AuditLog, User

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class NewUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    role: Literal["viewer", "analyst", "admin"] = "viewer"


@router.post("/login", dependencies=[Depends(rate_limit("login", 10))])
async def login(body: Login, response: Response, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    user = (await session.execute(select(User).where(User.email == body.email.lower()))).scalars().first()
    ok = bool(user and user.is_active and verify_password(body.password, user.password_hash))
    session.add(AuditLog(actor=body.email.lower(), actor_type="user", action="login_ok" if ok else "login_failed"))
    await session.commit()
    if not (ok and user):
        raise HTTPException(401, "invalid email or password")
    cfg = get_settings()
    response.set_cookie(COOKIE, make_token(user.email, user.role), max_age=cfg.jwt_ttl_hours * 3600, httponly=True,
                        samesite="lax", secure=cfg.app_env == "production", path="/")
    return {"email": user.email, "role": user.role}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    return {"email": user["sub"], "role": user["role"]}


@router.post("/users", status_code=201)
async def create_user(body: NewUser, admin: dict[str, Any] = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    session.add(User(email=body.email.lower(), password_hash=hash_password(body.password), role=body.role))
    session.add(AuditLog(actor=admin["sub"], actor_type="user", action="create_user", entity_id=body.email.lower(),
                         details={"role": body.role}))
    try:
        await session.commit()
    except IntegrityError:
        raise HTTPException(409, "email already registered") from None
    return {"email": body.email.lower(), "role": body.role}
