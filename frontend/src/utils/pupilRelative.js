// Converts annotation points between absolute frame-normalized coordinates (0-1,
// matching the video container as used throughout the rest of the app) and
// pupil-relative coordinates (offset from the pupil center, in units of the
// pupil's radius along each axis).
//
// Storing pupil-relative coordinates -- rather than absolute ones -- is what
// makes an annotation "stick" to the eye: resolving with the *current* pupil
// reading at render time reproduces the same offset from wherever the pupil
// has moved/resized to since the stroke was drawn, with no need to know the
// pupil's position at draw time again.
//
// x and y are scaled independently (by rx and ry respectively) rather than by
// a single uniform radius, to match AnnotationOverlay's 0-100 viewBox which is
// itself stretched non-uniformly (preserveAspectRatio="none") to fill the video
// container regardless of its aspect ratio.

// Used until the first pupil detection arrives (or if the stream isn't publishing
// pupil data at all): relative math degrades to a no-op, i.e. identical to plain
// frame-normalized coordinates.
export const DEFAULT_PUPIL = { cx: 0.5, cy: 0.5, rx: 1, ry: 1 }

export function toRelative(point, pupil) {
  const p = pupil ?? DEFAULT_PUPIL
  const rx = p.rx || DEFAULT_PUPIL.rx
  const ry = p.ry || DEFAULT_PUPIL.ry
  return {
    x: (point.x - p.cx) / rx,
    y: (point.y - p.cy) / ry,
  }
}

export function toAbsolute(point, pupil) {
  const p = pupil ?? DEFAULT_PUPIL
  return {
    x: p.cx + point.x * p.rx,
    y: p.cy + point.y * p.ry,
  }
}
