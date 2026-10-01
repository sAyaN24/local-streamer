import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from streammark_webserver.api.deps import get_current_user, get_settings, get_user_repo
from streammark_webserver.api.schemas import (
    AdminPasswordResetRequest,
    AuthResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
)
from streammark_shared.config import Settings
from streammark_webserver.security import hash_password, mint_session_token, verify_password
from streammark_webserver.db.repositories import UserRepository

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(
    body: UserSignupRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if await user_repo.get_by_email(body.email) is not None:
        raise HTTPException(409, "an account with this email already exists")

    doc = await user_repo.create(body.email, body.name, hash_password(body.password), role="user")
    token, ttl = mint_session_token(settings, doc["_id"], doc["email"])
    return AuthResponse(user=UserResponse.from_doc(doc), token=token, expires_in_seconds=ttl)


@router.post("/setup-admin", response_model=AuthResponse, status_code=201)
async def setup_admin(
    body: UserSignupRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """One-time bootstrap: creates the first admin account. Deliberately unauthenticated --
    there is no admin session to require yet on a fresh install -- but gated shut the moment
    any admin account exists, so it can never be used to mint a second admin later. Intended
    to be called exactly once, by infra/scripts/seed_admin.py during setup."""
    if await user_repo.admin_exists():
        raise HTTPException(409, "an admin account has already been set up")
    if await user_repo.get_by_email(body.email) is not None:
        raise HTTPException(409, "an account with this email already exists")

    doc = await user_repo.create(body.email, body.name, hash_password(body.password), role="admin")
    token, ttl = mint_session_token(settings, doc["_id"], doc["email"])
    return AuthResponse(user=UserResponse.from_doc(doc), token=token, expires_in_seconds=ttl)


@router.post("/reset-admin-password", status_code=204)
async def reset_admin_password(
    body: AdminPasswordResetRequest,
    x_setup_secret: str = Header(...),
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> None:
    """Resets an existing admin's password. Gated by X-Setup-Secret matching
    auth_jwt_secret rather than requiring a session -- the whole point is to recover
    when you don't have valid credentials. This adds no new exposure: anyone who
    already knows auth_jwt_secret can forge a valid admin session token with it
    directly (see security.mint_session_token/decode_session_token), so they already
    have full admin access; this just gives the box operator (who reads it straight
    out of infra/.env, same as every other secret there) a way to use that same
    standing trust to fix a lost/rotated password instead. Intended to be called by
    infra/scripts/seed_admin.py, and only when ADMIN_RESET=1 is explicitly set (see
    its own comment) -- never by the routine, unattended `docker compose up` a
    reboot triggers, or every reboot would silently change the admin's password."""
    if not secrets.compare_digest(x_setup_secret, settings.auth_jwt_secret):
        raise HTTPException(403, "invalid setup secret")

    doc = await user_repo.get_by_email(body.email)
    if doc is None or doc.get("role") != "admin":
        raise HTTPException(404, "no admin account with that email")

    await user_repo.set_password_hash(body.email, hash_password(body.new_password))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: UserLoginRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    doc = await user_repo.get_by_email(body.email)
    if doc is None or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(401, "invalid email or password")

    token, ttl = mint_session_token(settings, doc["_id"], doc["email"])
    return AuthResponse(user=UserResponse.from_doc(doc), token=token, expires_in_seconds=ttl)


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_doc(current_user)
