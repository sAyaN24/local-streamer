"""Headless data-channel-only participant that persists every annotation message.

Subscribes to a room's data channel only (never subscribes to video, never
publishes) and writes each message to MongoDB's `annotations` collection via
AnnotationRepository, plus stdout and an optional file for local debugging.
This turns the original "stub, no DB" extensibility hook from the initial
design into real persistence, enabling future replay/audit of a session.
"""

import argparse
import asyncio
import json
import logging
import signal
import time
from pathlib import Path
from typing import Any, TextIO

from livekit import rtc

from streammark.common.config import get_settings
from streammark.common.logging_setup import configure_logging
from streammark.common.tokens import mint_logger_bot_token
from streammark.db.client import create_client, ensure_indexes, get_database
from streammark.db.repositories import AnnotationRepository

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="streammark-logger-bot", description=__doc__)
    parser.add_argument("--room", required=True, help="Room name to observe")
    parser.add_argument(
        "--out", default=None, help="Optional file path to also append JSON lines to"
    )
    return parser


def _log_task_exception(task: "asyncio.Task[Any]") -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("failed to persist annotation event", extra={"error": str(exc)})


def _make_data_handler(room_name: str, annotation_repo: AnnotationRepository, out_file: TextIO | None):
    def _on_data(data_packet: rtc.DataPacket) -> None:
        # Only annotation events are persisted here -- e.g. the ~20Hz "pupil" topic
        # published by ingest/publisher.py is live telemetry only (annotations are
        # stored pupil-relative, so no pupil history is needed to replay them
        # correctly) and would otherwise flood this collection.
        if data_packet.topic != "annotation":
            return

        sender = data_packet.participant.identity if data_packet.participant else "unknown"
        ts = time.time()
        try:
            payload = json.loads(data_packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None

        record = {
            "ts": ts,
            "room": room_name,
            "sender": sender,
            "topic": data_packet.topic,
            "payload": payload,
        }
        logger.info("annotation event", extra=record)
        if out_file:
            out_file.write(json.dumps(record, default=str) + "\n")
            out_file.flush()

        task = asyncio.create_task(
            annotation_repo.insert_event(room_name, sender, data_packet.topic, payload, ts)
        )
        task.add_done_callback(_log_task_exception)

    return _on_data


async def run_logger_bot(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    mongo_client = create_client(settings)
    db = get_database(mongo_client, settings)
    await ensure_indexes(db)
    annotation_repo = AnnotationRepository(db)

    out_file = Path(args.out).open("a") if args.out else None
    stop_event = asyncio.Event()

    try:
        room = rtc.Room()
        room.on("data_received", _make_data_handler(args.room, annotation_repo, out_file))
        room.on("disconnected", lambda *_: stop_event.set())

        token = mint_logger_bot_token(settings, args.room)
        await room.connect(
            settings.livekit_url, token, options=rtc.RoomOptions(auto_subscribe=True)
        )
        logger.info("logger bot connected", extra={"room": args.room})

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        await room.disconnect()
    finally:
        if out_file:
            out_file.close()
        mongo_client.close()


def cli(argv: list[str] | None = None) -> None:
    asyncio.run(run_logger_bot(argv))


if __name__ == "__main__":
    cli()
