"""Dev-only dummy video publisher.

Loops a local sample video file into a LiveKit room so the frontend's viewer/
annotation flow can be checked against a real subscribed video track, without
needing a capture card attached. Same shape as the real streammark-ingest
publisher (src/streammark/ingest/publisher.py) but reads frames from a video
file via OpenCV instead of a /dev/videoN capture device.

Usage (from backend/, with the venv active, `docker compose up -d livekit mongo`,
and the API already running so the target room exists):

    python scripts/dummy_publisher.py --room demo-room --video /path/to/sample.mp4

DIAGNOSTIC BUILD: mints its own publish-only token with hidden=False (instead of the
real ingest service's common/tokens.py::mint_publisher_token, which sets hidden=True),
to test whether livekit-client fails to attach tracks published by a hidden participant
that joined before the viewer ("Tried to add a track for a participant, that's not
present" in the browser console). Does not touch tokens.py -- that affects the real
ingest pipeline and is a separate decision.
"""

import argparse
import asyncio
import sys

import cv2
from livekit import api, rtc

from streammark.common.config import get_settings

WIDTH, HEIGHT = 1280, 720


def mint_visible_publisher_token(settings, room: str, identity: str) -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=False,
        can_publish_data=False,
        hidden=False,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_grants(grants)
        .with_ttl(settings.publisher_token_ttl)
    )
    return token.to_jwt()


async def main(room_name: str, identity: str, video_path: str) -> None:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: could not open video file '{video_path}'.")
        sys.exit(1)

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0
    frame_delay = 1 / video_fps

    settings = get_settings()
    token = mint_visible_publisher_token(settings, room_name, identity)

    room = rtc.Room()
    print(f"Connecting to {settings.livekit_url} ...")
    await room.connect(settings.livekit_url, token)
    print(f"Joined room '{room_name}' as '{identity}'.")

    source = rtc.VideoSource(width=WIDTH, height=HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("dummy-feed", source)
    options = rtc.TrackPublishOptions(video_codec=rtc.VideoCodec.H264, simulcast=False)
    await room.local_participant.publish_track(track, options)
    print(f"Publishing '{video_path}' in a loop at {video_fps:.1f}fps. Ctrl+C to stop.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of video reached, looping back to start...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            if frame.shape[1] != WIDTH or frame.shape[0] != HEIGHT:
                frame = cv2.resize(frame, (WIDTH, HEIGHT))

            rgba_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            source.capture_frame(
                rtc.VideoFrame(width=WIDTH, height=HEIGHT, type=rtc.VideoBufferType.RGBA, data=rgba_frame.tobytes())
            )
            await asyncio.sleep(frame_delay)
    finally:
        cap.release()
        await room.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Loop a local video file into a LiveKit room for testing.")
    parser.add_argument("--room", default="demo-room", help="Room id to publish into (must already exist)")
    parser.add_argument("--identity", default="dummy-publisher")
    parser.add_argument("--video", default="sample.mp4", help="Path to a local video file to loop")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.room, args.identity, args.video))
    except KeyboardInterrupt:
        print("\nStopped.")
