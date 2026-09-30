"""Thin repository wrappers around raw Motor collections.

Documents are plain dicts (no ODM) -- Pydantic schemas in api/schemas.py handle
the dict<->API-response conversion at the route layer. Kept intentionally thin:
one small class per collection, no generic base-repository abstraction, since
there are only three collections and their query shapes don't overlap.
"""

import time
import uuid
from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase

RoomStatus = Literal["scheduled", "live", "ended"]


def new_id() -> str:
    return str(uuid.uuid4())


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["users"]

    async def create(self, email: str, name: str, password_hash: str) -> dict[str, Any]:
        doc = {
            "_id": new_id(),
            "email": email.lower(),
            "name": name,
            "password_hash": password_hash,
            "created_at": time.time(),
        }
        await self._col.insert_one(doc)
        return doc

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self._col.find_one({"email": email.lower()})

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        return await self._col.find_one({"_id": user_id})


class RoomRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["rooms"]

    async def create(
        self,
        room_id: str,
        title: str,
        host_id: str,
        host_name: str,
        status: RoomStatus,
    ) -> dict[str, Any]:
        now = time.time()
        doc = {
            "_id": room_id,
            "title": title,
            "host_id": host_id,
            "host_name": host_name,
            "status": status,
            "created_at": now,
            "started_at": now if status == "live" else None,
            "ended_at": None,
        }
        await self._col.insert_one(doc)
        return doc

    async def get(self, room_id: str) -> dict[str, Any] | None:
        return await self._col.find_one({"_id": room_id})

    async def list(self) -> list[dict[str, Any]]:
        return await self._col.find().sort("created_at", -1).to_list(length=None)

    async def set_status(
        self,
        room_id: str,
        status: RoomStatus,
        *,
        started_at: float | None = None,
        ended_at: float | None = None,
    ) -> None:
        update: dict[str, Any] = {"status": status}
        if started_at is not None:
            update["started_at"] = started_at
        if ended_at is not None:
            update["ended_at"] = ended_at
        await self._col.update_one({"_id": room_id}, {"$set": update})


class AnnotationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["annotations"]

    async def insert_event(
        self, room: str, sender: str, topic: str | None, payload: Any, ts: float
    ) -> None:
        await self._col.insert_one(
            {
                "_id": new_id(),
                "room": room,
                "sender": sender,
                "topic": topic,
                "payload": payload,
                "ts": ts,
            }
        )

    async def list_for_room(self, room: str) -> list[dict[str, Any]]:
        return await self._col.find({"room": room}).sort("ts", 1).to_list(length=None)
