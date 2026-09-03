import logging
import sys
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _platform_backend() -> int:
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_V4L2


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


def _detect_content_bounds(
    frame: np.ndarray, black_thresh: int = 12, min_content_frac: float = 0.04
) -> tuple[int, int, int, int] | None:
    """Finds the bounding box of actual picture content in `frame`, to trim solid
    black pillarbox/letterbox bars baked into the pixel data itself (e.g. a Mac's
    output resized/positioned within the capture card's negotiated resolution) --
    not CSS/browser letterboxing, which never reaches this code. A column/row
    counts as "content" once at least `min_content_frac` of its pixels are above
    `black_thresh`; deliberately low so a thin border isn't mistaken for content
    and real picture at the very edge is never cropped away. Returns None if the
    frame already has no meaningful border.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    cols = np.flatnonzero((gray > black_thresh).mean(axis=0) > min_content_frac)
    rows = np.flatnonzero((gray > black_thresh).mean(axis=1) > min_content_frac)
    if cols.size == 0 or rows.size == 0:
        return None
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    if x0 == 0 and y0 == 0 and x1 == w and y1 == h:
        return None
    return x0, y0, x1, y1


class CaptureDevice:
    """Wraps cv2.VideoCapture against a capture card (V4L2 on Linux, AVFoundation
    on macOS, DirectShow on Windows) with the latency knobs (buffer size 1,
    explicit FOURCC/resolution/fps) that keep the capture stage of the
    glass-to-glass budget as small as possible.

    Capture devices routinely clamp or ignore requested resolution/fps/pixel-format
    without erroring, so every requested value is read back after open() and any
    mismatch is logged as a warning — a real capture card's actual limits should
    surface immediately here instead of silently degrading quality downstream.
    """

    # Frames spent observing the border before committing to a crop -- unioned
    # across all of them so a single atypically-dark calibration frame can't
    # cause real picture content to get cropped away.
    _CROP_CALIBRATION_FRAMES = 15

    def __init__(self, device: str, width: int, height: int, fps: int, fourcc: str):
        self._device = device
        self._requested_width = width
        self._requested_height = height
        self._requested_fps = fps
        self._requested_fourcc = fourcc.upper()
        self._cap: cv2.VideoCapture | None = None
        self.profile: CaptureProfile | None = None
        self._crop_box: tuple[int, int, int, int] | None = None
        self._crop_frames_seen = 0

    def open(self) -> CaptureProfile:
        self._crop_box = None
        self._crop_frames_seen = 0

        cap = cv2.VideoCapture(_resolve_device(self._device), _platform_backend())
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
        """Returns the raw captured frame, unmodified -- this is what gets published,
        so viewers always see the true camera picture (borders included). See
        `crop_box` for the calibrated content region, which callers doing pixel
        analysis (pupil detection) should crop to themselves; `read()` never alters
        pixels so that region stays correctly aligned with what's on screen.
        """
        if self._cap is None or self.profile is None:
            raise CaptureReadError("capture device is not open")

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CaptureReadError("failed to read frame from capture device")

        if frame.shape[1] != self.profile.width or frame.shape[0] != self.profile.height:
            frame = cv2.resize(frame, (self.profile.width, self.profile.height))

        self._calibrate_crop_box(frame)
        return frame

    def _calibrate_crop_box(self, frame: np.ndarray) -> None:
        """Observes the first _CROP_CALIBRATION_FRAMES frames to find the solid
        black pillarbox/letterbox border (if any) baked into the source signal,
        unioned across all of them so a single atypically-dark frame can't shrink
        the detected content region. Does not touch the frame's pixels -- see
        `crop_box`.
        """
        if self._crop_frames_seen >= self._CROP_CALIBRATION_FRAMES:
            return

        bounds = _detect_content_bounds(frame)
        if bounds is not None:
            if self._crop_box is None:
                self._crop_box = bounds
            else:
                x0, y0, x1, y1 = self._crop_box
                bx0, by0, bx1, by1 = bounds
                self._crop_box = (min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1))
        self._crop_frames_seen += 1
        if self._crop_frames_seen == self._CROP_CALIBRATION_FRAMES:
            logger.info(
                "capture border crop calibrated",
                extra={"crop_box": self._crop_box, "frame_wh": (frame.shape[1], frame.shape[0])},
            )

    @property
    def crop_box(self) -> tuple[int, int, int, int] | None:
        """Calibrated (x0, y0, x1, y1) bounding box of actual picture content within
        the raw frame, in raw-frame pixel coordinates -- None until calibration
        finishes (_CROP_CALIBRATION_FRAMES) or if no meaningful border was found.
        """
        if self._crop_frames_seen < self._CROP_CALIBRATION_FRAMES:
            return None
        return self._crop_box

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
