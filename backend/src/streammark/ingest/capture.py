import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureProfile:
    width: int
    height: int
    fps: float
    fourcc: str


class CaptureError(RuntimeError):
    pass


class CaptureOpenError(CaptureError):
    pass


class CaptureReadError(CaptureError):
    pass


def _fourcc_to_int(fourcc: str) -> int:
    if len(fourcc) != 4:
        raise ValueError(f"fourcc must be exactly 4 characters, got {fourcc!r}")
    return cv2.VideoWriter_fourcc(*fourcc)


def _int_to_fourcc(value: int) -> str:
    return "".join(chr((value >> (8 * i)) & 0xFF) for i in range(4))


def _resolve_device(device: str) -> int | str:
    """CAPTURE_DEVICE may be a numeric index ("0") or a device path ("/dev/video0")."""
    try:
        return int(device)
    except ValueError:
        return device


class CaptureDevice:
    """Wraps cv2.VideoCapture against a V4L2 capture card with the latency knobs
    (buffer size 1, explicit FOURCC/resolution/fps) that keep the capture stage of
    the glass-to-glass budget as small as possible.

    V4L2 devices routinely clamp or ignore requested resolution/fps/pixel-format
    without erroring, so every requested value is read back after open() and any
    mismatch is logged as a warning — a real capture card's actual limits should
    surface immediately here instead of silently degrading quality downstream.
    """

    def __init__(self, device: str, width: int, height: int, fps: int, fourcc: str):
        self._device = device
        self._requested_width = width
        self._requested_height = height
        self._requested_fps = fps
        self._requested_fourcc = fourcc.upper()
        self._cap: cv2.VideoCapture | None = None
        self.profile: CaptureProfile | None = None

    def open(self) -> CaptureProfile:
        cap = cv2.VideoCapture(_resolve_device(self._device), cv2.CAP_V4L2)
        if not cap.isOpened():
            raise CaptureOpenError(f"failed to open capture device {self._device!r}")

        # Order matters on many V4L2 drivers: fourcc, then resolution, then fps,
        # then buffer size (some drivers reset buffer size on a format change).
        cap.set(cv2.CAP_PROP_FOURCC, _fourcc_to_int(self._requested_fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
        cap.set(cv2.CAP_PROP_FPS, self._requested_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        actual_fourcc = _int_to_fourcc(int(cap.get(cv2.CAP_PROP_FOURCC)))

        if (actual_width, actual_height) != (self._requested_width, self._requested_height):
            logger.warning(
                "capture resolution not honored by device",
                extra={
                    "requested_wh": (self._requested_width, self._requested_height),
                    "actual_wh": (actual_width, actual_height),
                },
            )
        if actual_fps <= 0 or abs(actual_fps - self._requested_fps) > 1.0:
            logger.warning(
                "capture fps not honored by device",
                extra={"requested_fps": self._requested_fps, "actual_fps": actual_fps},
            )
        if actual_fourcc != self._requested_fourcc:
            logger.warning(
                "capture fourcc not honored by device",
                extra={"requested_fourcc": self._requested_fourcc, "actual_fourcc": actual_fourcc},
            )

        profile = CaptureProfile(
            width=actual_width or self._requested_width,
            height=actual_height or self._requested_height,
            fps=actual_fps if actual_fps > 0 else float(self._requested_fps),
            fourcc=actual_fourcc,
        )
        logger.info(
            "capture device opened",
            extra={"device": self._device, "profile": profile.__dict__},
        )

        self._cap = cap
        self.profile = profile
        return profile

    def read(self) -> np.ndarray:
        if self._cap is None or self.profile is None:
            raise CaptureReadError("capture device is not open")

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CaptureReadError("failed to read frame from capture device")

        if frame.shape[1] != self.profile.width or frame.shape[0] != self.profile.height:
            frame = cv2.resize(frame, (self.profile.width, self.profile.height))

        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
