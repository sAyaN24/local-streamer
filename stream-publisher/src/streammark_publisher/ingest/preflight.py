"""Pre-flight check for a capture device: open it and verify it yields real
(non-black) frames before handing it to the publisher.

An open device is NOT proof of a usable feed. Interlaced sources (common on
capture cards, e.g. AverMedia in 1080i) make OpenCV's swscaler fail per frame
and hand back an all-zero buffer while read() still reports success -- the
feed then streams pure black with no error anywhere in the stack. Catching
that here, loudly, beats someone reporting "the video is blank" later.

Mirrors the embedded-python preflight step in infra/scripts/start_capture.sh.
"""

import sys
from dataclasses import dataclass

import cv2


@dataclass
class PreflightResult:
    ok: bool
    width: int
    height: int
    fps: float
    peak_pixel: int
    read_failures: int
    all_black_frames: int
    message: str


def _platform_backend() -> int:
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_V4L2


def check_device(
    device: str | int, width: int, height: int, fps: int, sample_frames: int = 15
) -> PreflightResult:
    cap = cv2.VideoCapture(device, _platform_backend())
    if not cap.isOpened():
        return PreflightResult(
            ok=False,
            width=0,
            height=0,
            fps=0.0,
            peak_pixel=0,
            read_failures=0,
            all_black_frames=0,
            message=f"could not open capture device {device!r}",
        )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)

    # Discard a few warm-up frames: many cards emit blank frames right after open.
    for _ in range(5):
        cap.read()

    blank = 0
    read_fail = 0
    peak = 0
    for _ in range(sample_frames):
        ok, frame = cap.read()
        if not ok or frame is None:
            read_fail += 1
            continue
        m = int(frame.max())
        peak = max(peak, m)
        if m == 0:
            blank += 1
    cap.release()

    if read_fail == sample_frames:
        return PreflightResult(
            ok=False,
            width=actual_w,
            height=actual_h,
            fps=actual_fps,
            peak_pixel=peak,
            read_failures=read_fail,
            all_black_frames=blank,
            message="device opened but returned no frames",
        )
    if peak == 0:
        return PreflightResult(
            ok=False,
            width=actual_w,
            height=actual_h,
            fps=actual_fps,
            peak_pixel=peak,
            read_failures=read_fail,
            all_black_frames=blank,
            message=(
                "every sampled frame was pure black (peak pixel value 0). This is "
                "the classic interlaced-source failure: OpenCV cannot deinterlace, "
                "so sws_scale returns a zeroed buffer while read() still reports "
                "success. Fix: set the source device to a PROGRESSIVE mode (1080p, "
                "not 1080i), or put a deinterlace stage in front of the capture."
            ),
        )

    return PreflightResult(
        ok=True,
        width=actual_w,
        height=actual_h,
        fps=actual_fps,
        peak_pixel=peak,
        read_failures=read_fail,
        all_black_frames=blank,
        message="live frames contain real picture data",
    )
