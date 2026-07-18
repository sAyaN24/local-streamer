import asyncio
import enum
import logging
from typing import Awaitable, Callable

from livekit import rtc

from streammark.common.config import Settings
from streammark.common.tokens import mint_publisher_token

logger = logging.getLogger(__name__)


class Backoff:
    def __init__(self, initial: float, maximum: float):
        self._initial = initial
        self._maximum = maximum
        self._current = initial

    def next(self) -> float:
        delay = self._current
        self._current = min(self._current * 2, self._maximum)
        return delay

    def reset(self) -> None:
        self._current = self._initial


class ConnectionState(enum.Enum):
    DISCONNECTED = enum.auto()
    CONNECTING = enum.auto()
    CONNECTED = enum.auto()
    RECONNECTING = enum.auto()
    STOPPED = enum.auto()


class ConnectionSupervisor:
    """Owns the rtc.Room lifecycle for the ingest publisher.

    Two independent failure domains exist in this service: capture-device failures
    (handled entirely inside the capture thread — see publisher.py) and LiveKit
    connection failures (handled here). The SDK provides no retry on room.connect()
    itself (it raises rtc.ConnectError on failure), so initial-connect retry is our
    responsibility; once connected, the SDK's own internal reconnect logic handles
    transient network blips (emitting "reconnecting"/"reconnected" events). We only
    rebuild the whole Room/VideoSource/LocalVideoTrack on a *terminal* "disconnected"
    event — i.e. once the SDK itself has given up on reconnecting.
    """

    def __init__(self, settings: Settings, room_name: str, identity: str = "ingest"):
        self._settings = settings
        self._room_name = room_name
        self._identity = identity
        self._stop_event = asyncio.Event()
        self.state = ConnectionState.DISCONNECTED

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopping(self) -> bool:
        return self._stop_event.is_set()

    async def run(self, on_room_ready: Callable[[rtc.Room], Awaitable[None]]) -> None:
        backoff = Backoff(
            self._settings.ingest_reconnect_initial_backoff_sec,
            self._settings.ingest_reconnect_max_backoff_sec,
        )

        while not self._stop_event.is_set():
            room = rtc.Room()
            terminal_disconnect = asyncio.Event()
            room.on("disconnected", lambda *_: terminal_disconnect.set())
            room.on("reconnecting", lambda *_: logger.warning("livekit connection reconnecting"))
            room.on("reconnected", lambda *_: logger.info("livekit connection reconnected"))

            token = mint_publisher_token(self._settings, self._room_name, self._identity)
            self.state = ConnectionState.CONNECTING
            try:
                await room.connect(
                    self._settings.livekit_url,
                    token,
                    options=rtc.RoomOptions(auto_subscribe=False),
                )
            except rtc.ConnectError as exc:
                delay = backoff.next()
                logger.error(
                    "initial connect failed, retrying",
                    extra={"error": str(exc), "retry_in_sec": delay},
                )
                await asyncio.sleep(delay)
                continue

            backoff.reset()
            self.state = ConnectionState.CONNECTED
            logger.info("connected to room", extra={"room": self._room_name})

            try:
                await on_room_ready(room)
            except Exception:
                logger.exception("on_room_ready raised, rebuilding session")

            stop_waiter = asyncio.ensure_future(self._stop_event.wait())
            disconnect_waiter = asyncio.ensure_future(terminal_disconnect.wait())
            _, pending = await asyncio.wait(
                {stop_waiter, disconnect_waiter}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

            await room.disconnect()

            if self._stop_event.is_set():
                self.state = ConnectionState.STOPPED
                break

            self.state = ConnectionState.RECONNECTING
            delay = backoff.next()
            logger.warning(
                "room terminally disconnected, rebuilding session",
                extra={"retry_in_sec": delay},
            )
            await asyncio.sleep(delay)
