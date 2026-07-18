from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from motor.motor_asyncio import AsyncIOMotorDatabase

from streammark.api.room_service import RoomServiceClient
from streammark.common.config import Settings, get_settings
from streammark.common.security import InvalidSessionTokenError, decode_session_token
from streammark.db.repositories import AnnotationRepository, RoomRepository, UserRepository

__all__ = [
    "get_settings",
    "get_room_service",
    "get_db",
    "get_room_repo",
    "get_user_repo",
    "get_annotation_repo",
    "get_current_user",
]

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_room_service(request: Request) -> RoomServiceClient:
    return request.app.state.room_service


async def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def get_room_repo(request: Request) -> RoomRepository:
    return request.app.state.room_repo


async def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


async def get_annotation_repo(request: Request) -> AnnotationRepository:
    return request.app.state.annotation_repo


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    user_repo: UserRepository = Depends(get_user_repo),
) -> dict[str, Any]:
    try:
        claims = decode_session_token(settings, credentials.credentials)
    except InvalidSessionTokenError as exc:
        raise HTTPException(401, "invalid or expired session token") from exc

    user = await user_repo.get_by_id(claims["sub"])
    if user is None:
        raise HTTPException(401, "user not found")
    return user
