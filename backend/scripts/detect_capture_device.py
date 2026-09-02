"""Auto-detect which OpenCV camera index/device path is the live capture card.

Windows: DirectShow enumeration order is device-manager order, which is *not*
reliably "webcam first, capture card last" - on plenty of machines the
built-in webcam enumerates after the USB capture card. So among indices that
actually open and yield a frame, each candidate's DirectShow friendly name
(via `pygrabber`) is scored against known webcam/capture-card name patterns
and the best-scoring candidate wins; ties fall back to the highest index
(most recently enumerated). If `pygrabber` isn't installed, or no candidate
name is informative, this falls back to the plain highest-index heuristic -
pass an explicit override to start_live.sh if that's wrong for your hardware.

Linux/macOS: probes /dev/video* nodes via V4L2 and picks the first one that
opens and yields a frame (matches the CAPTURE_DEVICE=/dev/video0 default for
single-capture-card boxes).

Prints exactly one line to stdout: the chosen device (index or path). All
diagnostic output goes to stderr so callers can safely capture stdout.
"""

import sys

import cv2

# Substrings (checked case-insensitively) that indicate a device is the
# laptop/desktop's built-in camera rather than an external capture card.
_WEBCAM_NAME_HINTS = (
    "integrated",
    "built-in",
    "built in",
    "internal camera",
    "facetime",
    "laptop camera",
    "front camera",
    "user-facing",
    "truevision",
    "hd webcam",
)

# Substrings indicating an external HDMI/USB capture card/dongle.
_CAPTURE_NAME_HINTS = (
    "capture",
    "hdmi",
    "avermedia",
    "elgato",
    "cam link",
    "startech",
    "ezcap",
    "usb video",
    "usb3",
    "usb2",
    "video grabber",
    "acasis",
    "ugreen",
    "grabber",
)


def _dshow_device_names() -> list[str] | None:
    """Best-effort DirectShow friendly-name enumeration, aligned with the index
    order cv2.VideoCapture(i, cv2.CAP_DSHOW) uses. Returns None if unavailable."""
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        print(
            "  (pygrabber not installed - falling back to highest-index guess; "
            "`pip install pygrabber` for name-aware detection)",
            file=sys.stderr,
        )
        return None
    try:
        return FilterGraph().get_input_devices()
    except Exception as exc:  # pragma: no cover - depends on local DirectShow state
        print(f"  (could not enumerate DirectShow device names: {exc})", file=sys.stderr)
        return None


def _score_name(name: str | None) -> int:
    if not name:
        return 0
    lowered = name.lower()
    score = 0
    if any(hint in lowered for hint in _CAPTURE_NAME_HINTS):
        score += 2
    if any(hint in lowered for hint in _WEBCAM_NAME_HINTS):
        score -= 2
    return score


def probe_windows(names: list[str] | None) -> list[int]:
    candidates = []
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        opened = cap.isOpened()
        ok = False
        if opened:
            ok, _ = cap.read()
        cap.release()
        name = names[i] if names and i < len(names) else None
        label = f" ({name})" if name else ""
        print(f"  index {i}{label}: opened={opened} readable={ok}", file=sys.stderr)
        if opened and ok:
            candidates.append(i)
    return candidates


def probe_posix() -> list[str]:
    import glob

    candidates = []
    for path in sorted(glob.glob("/dev/video*")):
        cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
        opened = cap.isOpened()
        ok = False
        if opened:
            ok, _ = cap.read()
        cap.release()
        print(f"  {path}: opened={opened} readable={ok}", file=sys.stderr)
        if opened and ok:
            candidates.append(path)
    return candidates


def choose_windows(candidates: list[int], names: list[str] | None) -> int:
    """Pick the external capture card among working indices: rank by name score
    (capture-card-like names win, webcam-like names lose), tie-break by highest
    index (matches the old default when no name info is available)."""

    def key(i: int) -> tuple[int, int]:
        name = names[i] if names and i < len(names) else None
        return (_score_name(name), i)

    ranked = sorted(candidates, key=key, reverse=True)
    chosen = ranked[0]

    if names:
        labeled = [(i, names[i] if i < len(names) else None) for i in candidates]
        print(f"Candidates: {labeled} -> chosen: {chosen}", file=sys.stderr)
    else:
        print(f"Candidates: {candidates} -> chosen: {chosen}", file=sys.stderr)

    return chosen


def main() -> None:
    print("Probing capture devices...", file=sys.stderr)
    if sys.platform == "win32":
        names = _dshow_device_names()
        candidates = probe_windows(names)
        if not candidates:
            print("No readable capture device found.", file=sys.stderr)
            sys.exit(1)
        chosen = choose_windows(candidates, names)
    else:
        candidates = probe_posix()
        if not candidates:
            print("No readable capture device found.", file=sys.stderr)
            sys.exit(1)
        # POSIX: first working node = conventional /dev/video0-style default.
        chosen = candidates[0]
        print(f"Candidates: {candidates} -> chosen: {chosen}", file=sys.stderr)

    print(chosen)


if __name__ == "__main__":
    main()
