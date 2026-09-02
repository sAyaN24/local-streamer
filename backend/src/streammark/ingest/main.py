import argparse
import asyncio
import logging
import signal
import sys

from streammark.common.config import get_settings
from streammark.common.logging_setup import configure_logging
from streammark.ingest.publisher import PublisherSession

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streammark-ingest",
        description="Capture-card video ingestion: publishes a live feed into a LiveKit room.",
    )
    parser.add_argument(
        "--room", default=None, help="Room name to publish into (defaults to DEFAULT_ROOM_NAME)"
    )
    parser.add_argument(
        "--device", default=None, help="Capture device path/index override (defaults to CAPTURE_DEVICE)"
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--bitrate-kbps", type=int, default=None)
    parser.add_argument(
        "--identity", default=None, help="Publisher participant identity (defaults to ingest-<room>)"
    )
    return parser


async def run_ingest(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    room_name = args.room or settings.default_room_name
    if args.device:
        settings.capture_device = args.device
    if args.width:
        settings.video_width = args.width
    if args.height:
        settings.video_height = args.height
    if args.fps:
        settings.video_fps = args.fps
    if args.bitrate_kbps:
        settings.video_bitrate_kbps = args.bitrate_kbps

    session = PublisherSession(settings, room_name, identity=args.identity)

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, session.stop)

    logger.info(
        "starting ingest", extra={"room": room_name, "device": settings.capture_device}
    )
    await session.run()


def cli(argv: list[str] | None = None) -> None:
    asyncio.run(run_ingest(argv))


if __name__ == "__main__":
    cli()
