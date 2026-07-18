import cv2
import numpy as np
from livekit import rtc


def bgr_to_rgba_frame(bgr: np.ndarray, width: int, height: int) -> rtc.VideoFrame:
    """Convert an OpenCV BGR frame to the RGBA rtc.VideoFrame LiveKit's VideoSource expects.

    Resizing here is a rare fallback only — CaptureDevice.read() already resizes to
    the negotiated profile, this guards any caller that bypasses it (e.g. tests).
    """
    if bgr.shape[1] != width or bgr.shape[0] != height:
        bgr = cv2.resize(bgr, (width, height))

    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    return rtc.VideoFrame(
        width=width,
        height=height,
        type=rtc.VideoBufferType.RGBA,
        data=rgba.tobytes(),
    )
