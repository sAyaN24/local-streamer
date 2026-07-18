import { VideoOff } from 'lucide-react'

// Placeholder standing in for the real live video/stream source.
// Swap the inner content for a <video>/player element when stream logic is wired up.
export default function VideoPlaceholder({ label = 'Waiting for stream…', className = '' }) {
  return (
    <div
      className={`relative flex h-full w-full items-center justify-center overflow-hidden rounded-xl bg-slate-900 ${className}`}
      style={{
        backgroundImage:
          'repeating-linear-gradient(45deg, rgba(255,255,255,0.03) 0px, rgba(255,255,255,0.03) 2px, transparent 2px, transparent 12px)',
      }}
    >
      <div className="flex flex-col items-center gap-3 text-slate-500">
        <VideoOff className="h-10 w-10" strokeWidth={1.5} />
        <p className="text-sm font-medium">{label}</p>
      </div>
      <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium text-slate-300 backdrop-blur">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
        No source connected
      </div>
    </div>
  )
}
