import logging
import time
from collections import deque
from dataclasses import dataclass, field


class RollingFpsCounter:
    def __init__(self, window_sec: float = 5.0):
        self._window_sec = window_sec
        self._timestamps: deque[float] = deque()

    def tick(self) -> None:
        now = time.monotonic()
        self._timestamps.append(now)
        cutoff = now - self._window_sec
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    @property
    def fps(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0
        span = self._timestamps[-1] - self._timestamps[0]
        if span <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / span


@dataclass
class IngestMetrics:
    captured_frames: int = 0
    published_frames: int = 0
    dropped_frames: int = 0
    pupil_checked_frames: int = 0
    pupil_found_frames: int = 0
    pupil_published_messages: int = 0
    capture_fps: RollingFpsCounter = field(default_factory=RollingFpsCounter)
    publish_fps: RollingFpsCounter = field(default_factory=RollingFpsCounter)

    def log_summary(self, logger: logging.Logger) -> None:
        logger.info(
            "ingest metrics",
            extra={
                "captured_frames": self.captured_frames,
                "published_frames": self.published_frames,
                "dropped_frames": self.dropped_frames,
                "capture_fps": round(self.capture_fps.fps, 1),
                "publish_fps": round(self.publish_fps.fps, 1),
                "pupil_checked_frames": self.pupil_checked_frames,
                "pupil_found_frames": self.pupil_found_frames,
                "pupil_published_messages": self.pupil_published_messages,
            },
        )
