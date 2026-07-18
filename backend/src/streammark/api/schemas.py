from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

RoomStatus = Literal["scheduled", "live", "ended"]


# --- Auth ---


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "UserResponse":
        return cls(
            id=doc["_id"],
            email=doc["email"],
            name=doc["name"],
            created_at=datetime.fromtimestamp(doc["created_at"], tz=timezone.utc),
        )


class AuthResponse(BaseModel):
    user: UserResponse
    token: str
    expires_in_seconds: int


# --- Rooms ---


class RoomCreateRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")
    title: str = Field(..., min_length=1, max_length=200)
    go_live: bool = False


class RoomResponse(BaseModel):
    id: str
    title: str
    host_id: str
    host_name: str
    status: RoomStatus
    num_participants: int = 0
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @classmethod
    def from_doc(cls, doc: dict[str, Any], *, num_participants: int = 0) -> "RoomResponse":
        return cls(
            id=doc["_id"],
            title=doc["title"],
            host_id=doc["host_id"],
            host_name=doc["host_name"],
            status=doc["status"],
            num_participants=num_participants,
            created_at=datetime.fromtimestamp(doc["created_at"], tz=timezone.utc),
            started_at=(
                datetime.fromtimestamp(doc["started_at"], tz=timezone.utc)
                if doc.get("started_at")
                else None
            ),
            ended_at=(
                datetime.fromtimestamp(doc["ended_at"], tz=timezone.utc)
                if doc.get("ended_at")
                else None
            ),
        )


class ViewerTokenResponse(BaseModel):
    identity: str
    room: str
    url: str
    token: str
    expires_in_seconds: int


class AnnotationEventResponse(BaseModel):
    sender: str
    ts: datetime
    payload: dict[str, Any]

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "AnnotationEventResponse":
        return cls(
            sender=doc["sender"],
            ts=datetime.fromtimestamp(doc["ts"], tz=timezone.utc),
            payload=doc["payload"],
        )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    livekit_reachable: bool
    mongo_reachable: bool
    version: str
