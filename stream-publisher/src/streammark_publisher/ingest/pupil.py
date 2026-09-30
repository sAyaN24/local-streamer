"""Pupil detection for the live ingest pipeline.

detect_pupil() below is ported unchanged (in method) from Vision/pupil_detector.py:
detects the pupil as the most circular, plausibly-sized dark blob near the frame
center rather than by a fixed color, since pupil appearance varies (black, brown,
or reddish "red reflex") between patients and lighting conditions.

PupilTracker wraps it with the frame-to-frame plausibility gate ported from
Vision/axis_tracker.py's _is_plausible_detection() (rejects an implausible pupil
"find" -- e.g. detect_pupil() locking onto an instrument shadow for a frame -- so
publishing doesn't jump to it) plus a detection-rate throttle, since running the
full detector on every captured frame is unnecessary work at capture-thread rate.
"""

import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

JUMP_FACTOR = 1.5                  # max plausible center jump, as a multiple of the larger radius
RADIUS_RATIO_BOUNDS = (0.6, 1.6)   # plausible frame-to-frame radius change ratio
MAX_CONSECUTIVE_REJECTS = 15       # after this many implausible "finds" in a row, trust the
                                    # detector again -- the eye/camera has likely genuinely moved


def detect_pupil(frame_bgr, min_radius_frac=0.06, max_radius_frac=0.35,
                  min_circularity=0.75, debug=False):
    """
    Detect the pupil in a single BGR frame.

    Args:
        frame_bgr: input image, BGR (as read by cv2.imread / VideoCapture).
        min_radius_frac / max_radius_frac: plausible pupil radius as a
            fraction of the frame's shorter side. Filters out both noise
            specks and large non-pupil dark regions (e.g. background).
            0.06 (rather than a smaller value) specifically excludes small
            circular artifacts like the gap between speculum retractor
            prongs, which are real pupils' most common look-alike in this
            footage but never occupy a meaningful fraction of the frame.
        min_circularity: minimum 4*pi*Area/Perimeter^2 to accept a blob
            as circular enough to be a pupil (rejects elongated shapes
            like instruments, sutures, eyelid margins).
        debug: if True, also returns the intermediate binary mask used
            for contour detection (useful for tuning).

    Returns:
        center (x, y) in original-frame pixel coords, or None if not found
        radius in original-frame pixels, or None if not found
        found: bool
        debug_mask: binary mask (only if debug=True), else None
    """
    h, w = frame_bgr.shape[:2]

    # Downscale for speed; a max dimension of ~640px is plenty for a
    # shape-based detector and keeps this fast enough for video/live use.
    scale = 640.0 / max(h, w) if max(h, w) > 640 else 1.0
    small = cv2.resize(frame_bgr, (int(w * scale), int(h * scale))) if scale != 1.0 else frame_bgr
    sh, sw = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)

    # Close small bright specular highlights that sit *inside* the dark
    # pupil (the microscope light reflex) so the pupil segments as one
    # solid blob instead of a dark ring with a hole in it.
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    gray_closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, close_kernel)

    # Pupil is typically the darkest sizeable region in frame -> inverse
    # Otsu threshold picks it out without needing a fixed color/brightness
    # value, so it adapts per-frame/per-patient.
    _, mask = cv2.threshold(gray_closed, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, clean_kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, clean_kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_r = min_radius_frac * min(sh, sw)
    max_r = max_radius_frac * min(sh, sw)
    frame_cx, frame_cy = sw / 2.0, sh / 2.0
    max_dist = np.hypot(frame_cx, frame_cy)

    best = None  # (score, center, radius)
    for c in contours:
        area = cv2.contourArea(c)
        if area < np.pi * min_r * min_r or area > np.pi * max_r * max_r:
            continue

        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0 or area / hull_area < 0.9:
            continue  # reject non-convex blobs (instrument tips, glare glued to shadow, etc.)

        if len(c) >= 5:
            # A least-squares ellipse fit hugs the actual boundary shape,
            # averaging out small bumps/notches in the contour (vessels,
            # compression artifacts). cv2.minEnclosingCircle instead sizes
            # itself to whichever single contour point sticks out furthest,
            # which tends to produce a visibly loose/off-center circle.
            (cx, cy), (minor_axis, major_axis), _angle = cv2.fitEllipse(c)
            radius = (major_axis + minor_axis) / 4.0  # average of the two semi-axes
        else:
            (cx, cy), radius = cv2.minEnclosingCircle(c)

        # Prefer large, circular, and centrally-located candidates. The
        # centrality term guards against small circular artifacts near the
        # frame edge (e.g. the gap between speculum retractor prongs) that
        # pass the filters above but are never where the surgeon is
        # actually keeping the eye framed.
        centrality = 1.0 - (np.hypot(cx - frame_cx, cy - frame_cy) / max_dist)
        score = area * circularity * (0.4 + 0.6 * centrality)
        if best is None or score > best[0]:
            best = (score, (cx, cy), radius)

    if best is None:
        return None, None, False, (mask if debug else None)

    _, (cx, cy), radius = best
    center = (cx / scale, cy / scale)
    radius = radius / scale

    return (float(center[0]), float(center[1])), float(radius), True, (mask if debug else None)


def _is_plausible_detection(center, radius, last_center, last_radius):
    dist = np.hypot(center[0] - last_center[0], center[1] - last_center[1])
    if dist > JUMP_FACTOR * max(radius, last_radius):
        return False
    ratio = radius / last_radius if last_radius else 1.0
    return RADIUS_RATIO_BOUNDS[0] <= ratio <= RADIUS_RATIO_BOUNDS[1]


class PupilTracker:
    """Stateful per-stream wrapper around detect_pupil() for the live ingest loop.

    Adds two things detect_pupil() itself doesn't have, both ported from
    Vision/axis_tracker.py's video loop:
      - plausibility gating, so a single-frame implausible "find" (e.g. an
        instrument shadow) doesn't yank the reported pupil position;
      - hold-last-known, so a brief miss (occlusion) doesn't blank the result.

    Also throttles how often the (relatively expensive) detector actually runs,
    independent of capture frame rate, via min_detect_interval_sec -- callers
    should still call update() every captured frame; between-throttle calls
    just return the held last-known state cheaply.
    """

    def __init__(self, min_detect_interval_sec: float = 0.0, **detect_kwargs):
        self._min_detect_interval_sec = min_detect_interval_sec
        self._detect_kwargs = detect_kwargs
        self._last_center: tuple[float, float] | None = None
        self._last_radius: float | None = None
        self._rejected_streak = 0
        self._last_detect_ts = 0.0

    def update(self, frame_bgr) -> tuple[tuple[float, float] | None, float | None, bool]:
        """Runs (or reuses the last) detection for one frame.

        Returns (center, radius, found) in original-frame pixel coords. found is
        True only when a plausible pupil is currently visible; center/radius are
        still populated with the last known values on a miss so callers can keep
        drawing/anchoring against them.
        """
        now = time.monotonic()
        if now - self._last_detect_ts < self._min_detect_interval_sec:
            return self._last_center, self._last_radius, False
        self._last_detect_ts = now

        center, radius, found, _ = detect_pupil(frame_bgr, **self._detect_kwargs)

        if found and self._last_center is not None:
            if _is_plausible_detection(center, radius, self._last_center, self._last_radius):
                self._rejected_streak = 0
            else:
                self._rejected_streak += 1
                if self._rejected_streak < MAX_CONSECUTIVE_REJECTS:
                    found = False  # implausible jump -- treat as a miss, hold last known
                else:
                    self._rejected_streak = 0  # accept it: assume the eye/camera really moved

        if found:
            self._last_center, self._last_radius = center, radius

        return self._last_center, self._last_radius, found
