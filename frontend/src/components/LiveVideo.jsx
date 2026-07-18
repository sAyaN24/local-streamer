import { useEffect, useRef } from 'react'

export default function LiveVideo({ track, className = '' }) {
  const videoRef = useRef(null)

  useEffect(() => {
    const el = videoRef.current
    if (!el || !track) return
    track.attach(el)
    return () => track.detach(el)
  }, [track])

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      className={`h-full w-full rounded-xl bg-black object-contain ${className}`}
    />
  )
}
