"""Single source of truth for every JWT/VideoGrants shape minted by this backend.

Three distinct token shapes exist, each with intentionally different grants:

- viewer:      subscribe video, publish annotation data only. Minted on demand by the
               API service for anyone joining a room to watch + annotate.
- publisher:   publish video only, never subscribes, never sends data. Minted
               in-process by the ingest service — NEVER exposed over HTTP, since
               handing out a can_publish=True token to an arbitrary LAN caller would
               let them hijack the video feed.
- logger_bot:  subscribe to the data channel only, hidden from the participant list.
               Used by tools/logger_bot.py, a stub extensibility hook for future
               annotation persistence/debugging.
"""

from livekit import api

from streammark.common.config import Settings


def mint_viewer_token(
    settings: Settings, room: str, identity: str, name: str | None = None
) -> tuple[str, int]:
    """Returns (jwt, ttl_seconds)."""
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=False,
        can_subscribe=True,
        can_publish_data=True,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name or identity)
        .with_grants(grants)
        .with_ttl(settings.viewer_token_ttl)
    )
    return token.to_jwt(), int(settings.viewer_token_ttl.total_seconds())


def mint_broadcaster_token(
    settings: Settings, room: str, identity: str, name: str | None = None
) -> tuple[str, int]:
    """Returns (jwt, ttl_seconds). Browser publisher: can publish video + subscribe + send data."""
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name or identity)
        .with_grants(grants)
        .with_ttl(settings.viewer_token_ttl)
    )
    return token.to_jwt(), int(settings.viewer_token_ttl.total_seconds())


def mint_publisher_token(settings: Settings, room: str, identity: str = "ingest") -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=False,
        can_publish_data=False,
        hidden=True,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_grants(grants)
        .with_ttl(settings.publisher_token_ttl)
    )
    return token.to_jwt()


def mint_logger_bot_token(settings: Settings, room: str, identity: str = "logger-bot") -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=False,
        can_subscribe=True,
        can_publish_data=False,
        hidden=True,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_grants(grants)
        .with_ttl(settings.publisher_token_ttl)
    )
    return token.to_jwt()
