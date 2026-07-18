from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from streammark import __version__
from streammark.api.deps import get_db, get_room_service
from streammark.api.room_service import RoomServiceClient, RoomServiceError
from streammark.api.schemas import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz(
    rs: RoomServiceClient = Depends(get_room_service),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> HealthResponse:
    try:
        await rs.list_rooms()
        livekit_reachable = True
    except RoomServiceError:
        livekit_reachable = False

    try:
        await db.command("ping")
        mongo_reachable = True
    except Exception:
        mongo_reachable = False

    reachable = livekit_reachable and mongo_reachable
    return HealthResponse(
        status="ok" if reachable else "degraded",
        livekit_reachable=livekit_reachable,
        mongo_reachable=mongo_reachable,
        version=__version__,
    )
