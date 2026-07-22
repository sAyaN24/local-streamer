from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

from streammark.api.room_service import RoomServiceClient
from streammark.api.routes.auth import router as auth_router
from streammark.api.routes.health import router as health_router
from streammark.api.routes.rooms import router as rooms_router
from streammark.common.config import get_settings
from streammark.common.logging_setup import configure_logging
from streammark.db.client import create_client, ensure_indexes, get_database
from streammark.db.repositories import AnnotationRepository, RoomRepository, UserRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    lkapi = api.LiveKitAPI(
        settings.livekit_server_url, settings.livekit_api_key, settings.livekit_api_secret
    )
    app.state.room_service = RoomServiceClient(lkapi)

    mongo_client = create_client(settings)
    db = get_database(mongo_client, settings)
    await ensure_indexes(db)
    app.state.db = db
    app.state.user_repo = UserRepository(db)
    app.state.room_repo = RoomRepository(db)
    app.state.annotation_repo = AnnotationRepository(db)

    app.state.settings = settings
    try:
        yield
    finally:
        await lkapi.aclose()
        mongo_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="StreamMark backend", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(rooms_router, prefix="/rooms", tags=["rooms"])
    app.include_router(health_router, tags=["health"])
    return app


app = create_app()
