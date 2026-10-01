"""One-shot "just run it" entry point: auto-detects the capture card, sanity-
checks it, and starts publishing -- no --device flag, no separate detect step.

This is the entry point packaged into the standalone streammark-publish
executable (see stream-publisher/packaging/) for machines that only run the
capture-card publisher and don't have the rest of the repo: connection
settings (LIVEKIT_URL/API key+secret/ROOM) come from a .env file placed next
to the executable (or the process environment); the capture device itself is
always auto-detected unless --device overrides it.

streammark-ingest (main.py) is untouched and keeps requiring an explicit
--device -- it's driven by infra/scripts/start_capture.sh, which already does
its own detection/preflight pass against CAPTURE_DEVICE before invoking it.
"""

import argparse
import asyncio
import logging
import signal
import sys
import traceback

from streammark_shared.config import get_settings
from streammark_shared.logging_setup import configure_logging
from streammark_publisher.ingest.device_detect import DeviceDetectionError, detect_device
from streammark_publisher.ingest.preflight import check_device
from streammark_publisher.ingest.publisher import PublisherSession

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streammark-publish",
        description=(
            "Auto-detects the capture card and starts publishing into a LiveKit "
            "room. Connection settings come from .env / the environment."
        ),
    )
    parser.add_argument(
        "--room", default=None, help="Room name to publish into (defaults to DEFAULT_ROOM_NAME)"
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Skip auto-detection and use this capture device index/path instead",
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--bitrate-kbps", type=int, default=None)
    parser.add_argument(
        "--identity", default=None, help="Publisher participant identity (defaults to ingest-<room>)"
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the open+non-black-frame sanity check and publish immediately",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Publish anyway even if the preflight check fails",
    )
    return parser


def _resolve_device(args: argparse.Namespace) -> str:
    if args.device:
        print(f"Using capture device override: {args.device}")
        return args.device

    print("Auto-detecting capture card...")
    try:
        device = detect_device()
    except DeviceDetectionError as exc:
        print(f"\nError: {exc}")
        print("  - Confirm the capture card is plugged in and not held by another app")
        print("    (OBS, QuickTime, Zoom, Teams, ...).")
        print("  - Or pass the device explicitly: streammark-publish --device 1")
        raise SystemExit(1) from None
    print(f"Detected capture device: {device}")
    return str(device)


def _run_preflight(
    device: str, width: int, height: int, fps: int, fourcc: str, force: bool
) -> None:
    print("\nChecking capture device (open + non-black frame check)...")
    result = check_device(device, width, height, fps, fourcc)
    print(
        f"  device={device} negotiated={result.width}x{result.height} @ {result.fps:.0f}fps "
        f"(requested {width}x{height} @ {fps})"
    )
    print(
        f"  sampled frames: read_failures={result.read_failures} "
        f"all_black={result.all_black_frames} peak_pixel={result.peak_pixel}"
    )
    if result.ok:
        print(f"  OK: {result.message}")
        return

    print(f"\n  FAIL: {result.message}")
    if force:
        print("  --force given: publishing anyway.")
        return
    print("\nAborting: the capture device would stream an unusable feed.")
    print("Fix the device and re-run, or pass --force to publish anyway.")
    raise SystemExit(2)


async def run_publish(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    room_name = args.room or settings.default_room_name
    if args.width:
        settings.video_width = args.width
    if args.height:
        settings.video_height = args.height
    if args.fps:
        settings.video_fps = args.fps
    if args.bitrate_kbps:
        settings.video_bitrate_kbps = args.bitrate_kbps

    device = _resolve_device(args)
    settings.capture_device = device

    if not args.skip_preflight:
        _run_preflight(
            device,
            settings.video_width,
            settings.video_height,
            settings.video_fps,
            settings.capture_fourcc,
            args.force,
        )

    session = PublisherSession(settings, room_name, identity=args.identity)

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, session.stop)

    print(f"\nPublishing into room '{room_name}' (Ctrl+C to stop)...")
    logger.info("starting auto-publish", extra={"room": room_name, "device": device})
    await session.run()


def cli(argv: list[str] | None = None) -> None:
    """Entry point for the packaged executable. Keeps the console window open
    on failure (double-clicking an .exe closes its window immediately on
    return, which would otherwise hide the error) and exits cleanly on
    Ctrl+C."""
    try:
        asyncio.run(run_publish(argv))
    except KeyboardInterrupt:
        print("\nStopped.")
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        if sys.platform == "win32" and sys.stdin is not None and sys.stdin.isatty():
            input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    cli()
