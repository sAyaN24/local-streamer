import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from streammark.api.deps import (
    get_annotation_repo,
    get_current_user,
    get_room_repo,
    get_room_service,
    get_settings,
)
from streammark.api.room_service import RoomServiceClient, RoomServiceError
from streammark.api.schemas import (
    AnnotationEventResponse,
    RoomCreateRequest,
    RoomResponse,
    ViewerTokenResponse,
)
from streammark.common.config import Settings
from streammark.common.tokens import mint_broadcaster_token, mint_viewer_token
from streammark.db.repositories import AnnotationRepository, RoomRepository

router = APIRouter()


def _require_host(room_doc: dict, current_user: dict) -> None:
    if room_doc["host_id"] != current_user["_id"]:
        raise HTTPException(403, "only the room's host can do this")


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(
    body: RoomCreateRequest,
    current_user: dict = Depends(get_current_user),
    room_repo: RoomRepository = Depends(get_room_repo),
    rs: RoomServiceClient = Depends(get_room_service),
    settings: Settings = Depends(get_settings),
) -> RoomResponse:
    if await room_repo.get(body.id) is not None:
        raise HTTPException(409, f"room '{body.id}' already exists")

    status = "live" if body.go_live else "scheduled"
    if body.go_live:
        try:
            await rs.create_room(
                body.id,
                empty_timeout=settings.room_empty_timeout_sec,
                departure_timeout=settings.room_departure_timeout_sec,
                max_participants=settings.room_max_participants,
            )
        except RoomServiceError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc

    doc = await room_repo.create(
        body.id, body.title, current_user["_id"], current_user["name"], status
    )
    return RoomResponse.from_doc(doc)


@router.post("/{room_id}/go-live", response_model=RoomResponse)
async def go_live(
    room_id: str,
    current_user: dict = Depends(get_current_user),
    room_repo: RoomRepository = Depends(get_room_repo),
    rs: RoomServiceClient = Depends(get_room_service),
    settings: Settings = Depends(get_settings),
) -> RoomResponse:
    doc = await room_repo.get(room_id)
    if doc is None:
        raise HTTPException(404, f"room '{room_id}' not found")
    _require_host(doc, current_user)
    if doc["status"] != "scheduled":
        raise HTTPException(409, f"room '{room_id}' is not in 'scheduled' state")

    try:
        await rs.create_room(
            room_id,
            empty_timeout=settings.room_empty_timeout_sec,
            departure_timeout=settings.room_departure_timeout_sec,
            max_participants=settings.room_max_participants,
        )
    except RoomServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    started_at = time.time()
    await room_repo.set_status(room_id, "live", started_at=started_at)
    doc["status"] = "live"
    doc["started_at"] = started_at
    return RoomResponse.from_doc(doc)


@router.get("", response_model=list[RoomResponse])
async def list_rooms(
    room_repo: RoomRepository = Depends(get_room_repo),
    rs: RoomServiceClient = Depends(get_room_service),
) -> list[RoomResponse]:
    docs = await room_repo.list()

    live_counts: dict[str, int] = {}
    if any(doc["status"] == "live" for doc in docs):
        try:
            live_rooms = await rs.list_rooms()
            live_counts = {r.name: r.num_participants for r in live_rooms}
        except RoomServiceError:
            live_counts = {}

    return [
        RoomResponse.from_doc(doc, num_participants=live_counts.get(doc["_id"], 0))
        for doc in docs
    ]


@router.delete("/{room_id}", status_code=204)
async def end_room(
    room_id: str,
    current_user: dict = Depends(get_current_user),
    room_repo: RoomRepository = Depends(get_room_repo),
    rs: RoomServiceClient = Depends(get_room_service),
) -> None:
    doc = await room_repo.get(room_id)
    if doc is None:
        raise HTTPException(404, f"room '{room_id}' not found")
    _require_host(doc, current_user)

    if doc["status"] == "live":
        try:
            await rs.delete_room(room_id)
        except RoomServiceError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc

    await room_repo.set_status(room_id, "ended", ended_at=time.time())


@router.get("/{room_id}/token", response_model=ViewerTokenResponse)
async def get_viewer_token(
    room_id: str,
    identity: str | None = Query(default=None),
    display_name: str | None = Query(default=None, alias="name"),
    settings: Settings = Depends(get_settings),
) -> ViewerTokenResponse:
    """Mints a viewer join token. Deliberately does not check room existence in
    Mongo or LiveKit first -- token minting is a pure local JWT operation, and
    checking would just add a network round trip for no real benefit (a token
    for a nonexistent/ended room simply fails to connect client-side)."""
    viewer_identity = identity or f"viewer-{uuid.uuid4().hex[:8]}"
    jwt_token, ttl = mint_viewer_token(settings, room_id, viewer_identity, display_name)
    return ViewerTokenResponse(
        identity=viewer_identity,
        room=room_id,
        url=settings.livekit_url,
        token=jwt_token,
        expires_in_seconds=ttl,
    )


@router.get("/{room_id}/broadcaster-token", response_model=ViewerTokenResponse)
async def get_broadcaster_token(
    room_id: str,
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ViewerTokenResponse:
    identity = current_user["_id"]
    name = current_user.get("name") or identity
    jwt_token, ttl = mint_broadcaster_token(settings, room_id, identity, name)
    return ViewerTokenResponse(
        identity=identity,
        room=room_id,
        url=settings.livekit_url,
        token=jwt_token,
        expires_in_seconds=ttl,
    )


@router.get("/{room_id}/annotations", response_model=list[AnnotationEventResponse])
async def list_room_annotations(
    room_id: str,
    annotation_repo: AnnotationRepository = Depends(get_annotation_repo),
) -> list[AnnotationEventResponse]:
    """Chronological annotation history for a room, persisted by tools/logger_bot.py off
    the LiveKit data channel. Powers late-joiner catch-up today; also the intended source
    for future recording/annotation-replay sync (payload.ts is the drawer's client-side
    timestamp, this response's top-level ts is when the logger bot received it)."""
    docs = await annotation_repo.list_for_room(room_id)
    return [
        AnnotationEventResponse.from_doc(doc)
        for doc in docs
        if doc.get("topic") == "annotation" and doc.get("payload") is not None
    ]
