// Renders live annotation strokes on top of the video. Coordinates in each stroke's `points`
// are normalized 0-1 relative to the container; the svg's 0-100 viewBox (stretched to fill via
// preserveAspectRatio="none") maps them 1:1 regardless of the container's actual pixel size.
export default function AnnotationOverlay({ strokes = [], colorForUser, visible = true }) {
  if (!visible) return null

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      {strokes.map((stroke) => {
        const color = stroke.color ?? colorForUser?.(stroke.userId) ?? '#f43f5e'
        return <Stroke key={stroke.strokeId} stroke={stroke} color={color} />
      })}
    </svg>
  )
}

function Stroke({ stroke, color }) {
  const points = (stroke.points ?? []).map((p) => ({ x: p.x * 100, y: p.y * 100 }))
  if (points.length === 0) return null

  if (stroke.tool === 'pen') {
    if (points.length < 2) return null
    const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
    return <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
  }

  if (stroke.tool === 'rectangle') {
    const [a, b] = points.length > 1 ? points : [points[0], points[0]]
    const x = Math.min(a.x, b.x)
    const y = Math.min(a.y, b.y)
    return (
      <rect
        x={x}
        y={y}
        width={Math.abs(b.x - a.x)}
        height={Math.abs(b.y - a.y)}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
    )
  }

  if (stroke.tool === 'circle') {
    const [a, b] = points.length > 1 ? points : [points[0], points[0]]
    const cx = (a.x + b.x) / 2
    const cy = (a.y + b.y) / 2
    const rx = Math.abs(b.x - a.x) / 2
    const ry = Math.abs(b.y - a.y) / 2
    return (
      <ellipse
        cx={cx}
        cy={cy}
        rx={rx || 0.5}
        ry={ry || 0.5}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
    )
  }

  if (stroke.tool === 'arrow') {
    const a = points[0]
    const b = points[points.length - 1]
    const markerId = `arrowhead-${stroke.strokeId}`
    return (
      <g>
        <defs>
          <marker id={markerId} markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L6,3 L0,6 Z" fill={color} />
          </marker>
        </defs>
        <line
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          stroke={color}
          strokeWidth={1.5}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          markerEnd={`url(#${markerId})`}
        />
      </g>
    )
  }

  if (stroke.tool === 'text') {
    const p = points[0]
    return (
      <text x={p.x} y={p.y} fill={color} fontSize="3" fontWeight="600" className="font-sans">
        {stroke.text}
      </text>
    )
  }

  return null
}
