from livekit import api
from livekit.protocol.models import Room as ProtoRoom


class RoomServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class RoomServiceClient:
    """Thin wrapper around api.LiveKitAPI().room, translating twirp errors into
    RoomServiceError so route handlers don't need to know about the transport."""

    def __init__(self, lkapi: api.LiveKitAPI):
        self._lkapi = lkapi

    async def create_room(
        self,
        name: str,
        *,
        empty_timeout: int,
        departure_timeout: int,
        max_participants: int,
        metadata: str = "",
    ) -> ProtoRoom:
        try:
            return await self._lkapi.room.create_room(
                api.CreateRoomRequest(
                    name=name,
                    empty_timeout=empty_timeout,
                    departure_timeout=departure_timeout,
                    max_participants=max_participants,
                    metadata=metadata,
                )
            )
        except api.TwirpError as exc:
            raise RoomServiceError(f"create_room failed: {exc}", status_code=exc.status) from exc

    async def list_rooms(self, names: list[str] | None = None) -> list[ProtoRoom]:
        try:
            resp = await self._lkapi.room.list_rooms(api.ListRoomsRequest(names=names or []))
        except api.TwirpError as exc:
            raise RoomServiceError(f"list_rooms failed: {exc}", status_code=exc.status) from exc
        return list(resp.rooms)

    async def get_room(self, name: str) -> ProtoRoom | None:
        rooms = await self.list_rooms(names=[name])
        return rooms[0] if rooms else None

    async def delete_room(self, name: str) -> None:
        try:
            await self._lkapi.room.delete_room(api.DeleteRoomRequest(room=name))
        except api.TwirpError as exc:
            raise RoomServiceError(f"delete_room failed: {exc}", status_code=exc.status) from exc
