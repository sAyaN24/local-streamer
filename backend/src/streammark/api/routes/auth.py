from fastapi import APIRouter, Depends, HTTPException

from streammark.api.deps import get_current_user, get_settings, get_user_repo
from streammark.api.schemas import (
    AuthResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
)
from streammark.common.config import Settings
from streammark.common.security import hash_password, mint_session_token, verify_password
from streammark.db.repositories import UserRepository

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(
    body: UserSignupRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if await user_repo.get_by_email(body.email) is not None:
        raise HTTPException(409, "an account with this email already exists")

    doc = await user_repo.create(body.email, body.name, hash_password(body.password))
    token, ttl = mint_session_token(settings, doc["_id"], doc["email"])
    return AuthResponse(user=UserResponse.from_doc(doc), token=token, expires_in_seconds=ttl)


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
