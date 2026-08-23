// Visual reference for what annotations are anchored to: the detected pupil's circle plus a
// screen-aligned X/Y axis through its center. Mirrors Vision/pupil_detector.py's draw_pupil()/
// draw_axes() (called from Vision/axis_tracker.py, the screen-aligned -- not rotation-tracking --
// variant), rebuilt as an SVG overlay using the same 0-100 stretched viewBox as AnnotationOverlay
// so its coordinate math is consistent with strokes drawn relative to it.
export default function PupilOverlay({ pupil, visible = true }) {
  if (!visible || !pupil) return null

  const cx = pupil.cx * 100
  const cy = pupil.cy * 100
  const rx = pupil.rx * 100
  const ry = pupil.ry * 100
  // Dimmed while holding a stale reading (found: false) -- pupil momentarily lost
  // (e.g. instrument occlusion) rather than genuinely gone.
  const opacity = pupil.found ? 0.9 : 0.35

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden="true"
      style={{ opacity }}
    >
      <line x1={0} y1={cy} x2={100} y2={cy} stroke="#22d3ee" strokeWidth={0.3} vectorEffect="non-scaling-stroke" />
      <line x1={cx} y1={0} x2={cx} y2={100} stroke="#22d3ee" strokeWidth={0.3} vectorEffect="non-scaling-stroke" />
      <ellipse
        cx={cx}
        cy={cy}
        rx={rx}
        ry={ry}
        fill="none"
        stroke="#22d3ee"
        strokeWidth={0.6}
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={`M${cx - 1.2},${cy} L${cx + 1.2},${cy} M${cx},${cy - 1.2} L${cx},${cy + 1.2}`}
        stroke="#22d3ee"
        strokeWidth={0.4}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
