import asyncio
import logging
import queue
import threading

from livekit import rtc

from streammark.common.config import Settings
from streammark.ingest.capture import CaptureDevice, CaptureError, CaptureOpenError
from streammark.ingest.frame_convert import bgr_to_rgba_frame
from streammark.ingest.metrics import IngestMetrics
from streammark.ingest.reconnect import ConnectionSupervisor

logger = logging.getLogger(__name__)

_CODEC_MAP = {
    "h264": rtc.VideoCodec.H264,
    "vp8": rtc.VideoCodec.VP8,
    "vp9": rtc.VideoCodec.VP9,
    "av1": rtc.VideoCodec.AV1,
}


def _get_with_timeout(q: "queue.Queue[rtc.VideoFrame]", timeout: float) -> rtc.VideoFrame | None:
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return None


class PublisherSession:
    """Wires a CaptureDevice (blocking, dedicated OS thread) to a LiveKit
    rtc.VideoSource publish loop (asyncio) via a depth-1 drop-oldest queue.

    cv2.VideoCapture.read() is a blocking call; running it directly on the asyncio
    event loop that also owns the LiveKit Room's internal reconnect/keepalive tasks
    would starve those tasks and degrade both latency and connection stability. The
    capture thread and the publish loop are therefore fully decoupled: a capture
    hiccup never tears down the WebRTC session, and a network blip never touches
    the capture device.
    """

    def __init__(self, settings: Settings, room_name: str, identity: str | None = None):
        self._settings = settings
        self._room_name = room_name
        self._identity = identity or f"ingest-{room_name}"
        self._metrics = IngestMetrics()
        self._frame_queue: "queue.Queue[rtc.VideoFrame]" = queue.Queue(maxsize=1)
        self._capture_stop = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._supervisor = ConnectionSupervisor(settings, room_name, self._identity)

    def stop(self) -> None:
        self._capture_stop.set()
        self._supervisor.stop()

    async def run(self) -> None:
        self._start_capture_thread()
        metrics_task = asyncio.create_task(self._metrics_loop())
        try:
            await self._supervisor.run(self._on_room_ready)
        finally:
            self._capture_stop.set()
            metrics_task.cancel()
            if self._capture_thread:
                self._capture_thread.join(timeout=5)

    def _start_capture_thread(self) -> None:
        device = CaptureDevice(
            device=self._settings.capture_device,
            width=self._settings.video_width,
            height=self._settings.video_height,
            fps=self._settings.video_fps,
            fourcc=self._settings.capture_fourcc,
        )
        self._capture_thread = threading.Thread(
            target=self._capture_loop, args=(device,), daemon=True, name="capture"
        )
        self._capture_thread.start()

    def _capture_loop(self, device: CaptureDevice) -> None:
        consecutive_failures = 0
        try:
            device.open()
        except CaptureOpenError:
            logger.exception("initial capture device open failed")

        while not self._capture_stop.is_set():
            try:
                if not device.is_opened:
                    device.open()
                bgr = device.read()
                consecutive_failures = 0
            except CaptureError:
                consecutive_failures += 1
                logger.warning(
                    "capture read failed", extra={"consecutive_failures": consecutive_failures}
                )
                if (
                    consecutive_failures
                    >= self._settings.ingest_capture_max_consecutive_read_failures
                ):
                    logger.error("capture device unresponsive, reopening")
                    device.release()
                    self._capture_stop.wait(self._settings.ingest_capture_reopen_interval_sec)
                    consecutive_failures = 0
                continue

            assert device.profile is not None
            frame = bgr_to_rgba_frame(bgr, device.profile.width, device.profile.height)
            self._metrics.captured_frames += 1
            self._metrics.capture_fps.tick()

            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                    self._metrics.dropped_frames += 1
                except queue.Empty:
                    pass
            try:
                self._frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        device.release()

    async def _on_room_ready(self, room: rtc.Room) -> None:
        width = self._settings.video_width
        height = self._settings.video_height

        source = rtc.VideoSource(width=width, height=height)
        track = rtc.LocalVideoTrack.create_video_track(f"{self._room_name}-source", source)

        options = rtc.TrackPublishOptions(
            video_codec=_CODEC_MAP[self._settings.video_codec],
            simulcast=self._settings.simulcast_enabled,
            video_encoding=rtc.VideoEncoding(
                max_bitrate=self._settings.video_bitrate_kbps * 1000,
                max_framerate=float(self._settings.video_fps),
            ),
            source=rtc.TrackSource.SOURCE_CAMERA,
        )

        await room.local_participant.publish_track(track, options)
        logger.info("video track published", extra={"width": width, "height": height})

        await self._publish_loop(room, source)

    async def _publish_loop(self, room: rtc.Room, source: rtc.VideoSource) -> None:
        loop = asyncio.get_running_loop()
        frame_period = 1.0 / self._settings.video_fps
        next_deadline = loop.time()

        while (
            not self._capture_stop.is_set()
            and not self._supervisor.stopping
            and room.connection_state != rtc.ConnectionState.CONN_DISCONNECTED
        ):
            frame = await asyncio.to_thread(_get_with_timeout, self._frame_queue, 1.0)
            if frame is None:
                continue

            source.capture_frame(frame)
            self._metrics.published_frames += 1
            self._metrics.publish_fps.tick()

            next_deadline += frame_period
            delay = next_deadline - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                next_deadline = loop.time()

    async def _metrics_loop(self) -> None:
        while True:
            await asyncio.sleep(self._settings.metrics_log_interval_sec)
            self._metrics.log_summary(logger)
