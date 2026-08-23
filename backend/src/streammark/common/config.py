from datetime import timedelta
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Shared configuration for the api, ingest, and tools entrypoints.

    LiveKit connection fields deliberately have no env-var prefix so they also
    satisfy livekit-api's own built-in LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET
    env fallback used by api.AccessToken()/api.LiveKitAPI() when called with no args.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # --- LiveKit connection ---
    # livekit_url is the URL handed to browsers via /rooms/*/viewer-token, so it
    # must be reachable from LAN clients (typically the host's LAN IP).
    # livekit_url_internal is what this process itself uses for server-to-server
    # calls; falls back to livekit_url when unset. Split because on Docker
    # Desktop, containers can't route to the Mac/Windows host's LAN IP but can
    # reach sibling containers by service name.
    livekit_url: str = "ws://localhost:7880"
    livekit_url_internal: str | None = None
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret-please-change-before-deploy"

    # --- Capture device ---
    capture_device: str = "/dev/video0"
    capture_fourcc: str = "MJPG"

    # --- Video profile ---
    video_width: int = 1920
    video_height: int = 1080
    video_fps: int = 60
    video_bitrate_kbps: int = 8000
    video_codec: Literal["h264", "vp8", "vp9", "av1"] = "h264"
    simulcast_enabled: bool = False

    # --- Room defaults ---
    default_room_name: str = "shared-stream"
    room_empty_timeout_sec: int = 300
    room_departure_timeout_sec: int = 20
    room_max_participants: int = 60

    # --- Tokens (LiveKit) ---
    viewer_token_ttl_minutes: int = 360
    publisher_token_ttl_minutes: int = 720

    # --- MongoDB ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "streammark"

    # --- App-level auth (separate secret from LiveKit's -- these tokens are never
    # accepted by livekit-server, only by this API's own get_current_user dependency) ---
    auth_jwt_secret: str = "devauthsecret-please-change-before-deploy"
    auth_token_ttl_minutes: int = 1440

    # --- API service ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # NoDecode: without it, pydantic-settings tries to JSON-decode this env var before
    # _split_csv ever runs, so the documented CORS_ALLOW_ORIGINS=* crashes startup with a
    # JSONDecodeError instead of being CSV-split.
    cors_allow_origins: Annotated[list[str], NoDecode] = ["*"]
    log_level: str = "INFO"

    # --- Ingest resilience/observability ---
    ingest_reconnect_initial_backoff_sec: float = 0.5
    ingest_reconnect_max_backoff_sec: float = 10.0
    ingest_capture_reopen_interval_sec: float = 2.0
    ingest_capture_max_consecutive_read_failures: int = 30
    metrics_log_interval_sec: float = 5.0

    # --- Pupil tracking ---
    # Detected once per capture frame (throttled by pupil_detect_min_interval_sec) and
    # broadcast to viewers over the LiveKit data channel so annotations can be anchored
    # to the pupil's live position/size instead of raw frame coordinates.
    pupil_detection_enabled: bool = True
    pupil_detect_min_interval_sec: float = 0.05  # caps detector to ~20Hz regardless of capture fps
    pupil_publish_interval_sec: float = 0.05     # caps data-channel publish rate to ~20Hz
    pupil_min_radius_frac: float = 0.06
    pupil_max_radius_frac: float = 0.35
    pupil_min_circularity: float = 0.75

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def livekit_server_url(self) -> str:
        return self.livekit_url_internal or self.livekit_url

    @property
    def viewer_token_ttl(self) -> timedelta:
        return timedelta(minutes=self.viewer_token_ttl_minutes)

    @property
    def publisher_token_ttl(self) -> timedelta:
        return timedelta(minutes=self.publisher_token_ttl_minutes)

    @property
    def auth_token_ttl(self) -> timedelta:
        return timedelta(minutes=self.auth_token_ttl_minutes)


@lru_cache
def get_settings() -> Settings:
    return Settings()
