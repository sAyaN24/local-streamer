import { useEffect, useRef, useState } from 'react'
import { Room, RoomEvent, Track } from 'livekit-client'

// Every browser participant joins as a subscribe-only viewer (backend never issues a
// can_publish=true token to browsers) — this hook never publishes camera/mic tracks.
export function useLiveKitRoom({ url, token }) {
  const roomRef = useRef(null)
  const [status, setStatus] = useState('connecting')
  const [videoTrack, setVideoTrack] = useState(null)
  const [remoteParticipants, setRemoteParticipants] = useState([])
  const [localParticipant, setLocalParticipant] = useState(null)

  useEffect(() => {
    if (!url || !token) return

    const room = new Room()
    roomRef.current = room
    let cancelled = false

    const syncParticipants = () => {
      setRemoteParticipants(Array.from(room.remoteParticipants.values()))
    }

    room.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === Track.Kind.Video) setVideoTrack(track)
    })
    room.on(RoomEvent.TrackUnsubscribed, (track) => {
      if (track.kind === Track.Kind.Video) {
        setVideoTrack((current) => (current === track ? null : current))
      }
    })
    room.on(RoomEvent.ParticipantConnected, syncParticipants)
    room.on(RoomEvent.ParticipantDisconnected, syncParticipants)
    room.on(RoomEvent.Disconnected, () => {
      if (!cancelled) setStatus('disconnected')
    })

    room
      .connect(url, token)
      .then(() => {
        if (cancelled) return
        setStatus('connected')
        setLocalParticipant(room.localParticipant)
        syncParticipants()
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })

    return () => {
      cancelled = true
      room.disconnect()
      roomRef.current = null
    }
  }, [url, token])

  return { room: roomRef.current, status, videoTrack, remoteParticipants, localParticipant }
}
