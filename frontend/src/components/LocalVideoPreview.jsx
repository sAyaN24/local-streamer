import { useEffect, useRef } from 'react'

export default function LocalVideoPreview({ track }) {
  const videoRef = useRef(null)

  useEffect(() => {
    const el = videoRef.current
    if (!el || !track) return
    track.attach(el)
    return () => track.detach(el)
  }, [track])

  return (
    <div className="absolute bottom-4 left-3 w-36 overflow-hidden rounded-lg border border-slate-700 bg-black shadow-lg sm:left-4 sm:w-44">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="h-full w-full object-cover"
        style={{ transform: 'scaleX(-1)' }}
      />
      <span className="absolute bottom-1 left-2 text-[10px] font-medium text-white/70">You</span>
    </div>
  )
}
