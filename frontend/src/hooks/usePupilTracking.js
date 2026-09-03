import { useEffect, useState } from 'react'
import { RoomEvent } from 'livekit-client'

// Consumes the "pupil" data-channel topic published by backend/ingest/publisher.py
// (PupilTracker, once per captured frame -- ~capture fps). Payload: { found, cx, cy, rx, ry, ts } all normalized 0-1,
// cx/cy relative to frame width/height and rx/ry the pupil radius as a fraction of
// frame width/height respectively (independent per-axis, matching the annotation
// overlay's non-uniform stretch) -- see utils/pupilRelative.js for how these are
// used to anchor annotation points to the pupil.
const PUPIL_TOPIC = 'pupil'
const decoder = new TextDecoder()

export function usePupilTracking({ room }) {
  const [pupil, setPupil] = useState(null)

  useEffect(() => {
    if (!room) return
    const handleData = (payload, _participant, _kind, topic) => {
      if (topic !== PUPIL_TOPIC) return
      let message
      try {
        message = JSON.parse(decoder.decode(payload))
      } catch {
        return
      }
      // Hold the last known center/radius on a miss (found: false) rather than
      // clearing it, mirroring PupilTracker's hold-last-known behavior server-side --
      // a brief occlusion shouldn't yank annotations back to the frame origin.
      setPupil((current) => {
        if (message.found) return message
        if (!current) return message
        return { ...current, found: false, ts: message.ts }
      })
    }
    room.on(RoomEvent.DataReceived, handleData)
    return () => room.off(RoomEvent.DataReceived, handleData)
  }, [room])

  return pupil
}
