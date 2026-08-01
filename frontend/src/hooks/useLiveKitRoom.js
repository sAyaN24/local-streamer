import { useEffect, useRef, useState } from 'react'
import { createLocalVideoTrack, Room, RoomEvent, Track } from 'livekit-client'

export function useLiveKitRoom({ url, token, publishWebcam = false, videoDeviceId = null }) {
  const roomRef = useRef(null)
  const [status, setStatus] = useState('connecting')
  const [videoTrack, setVideoTrack] = useState(null)
  const [remoteParticipants, setRemoteParticipants] = useState([])
  const [localParticipant, setLocalParticipant] = useState(null)
  const [localVideoTrack, setLocalVideoTrack] = useState(null)

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
      // Reset so the publishing effect re-fires correctly when a new room connects.
      setStatus('connecting')
      setVideoTrack(null)
      setLocalParticipant(null)
      setRemoteParticipants([])
    }
  }, [url, token])

  useEffect(() => {
    const room = roomRef.current
    if (status !== 'connected' || !publishWebcam || !room) return

    let track = null
    let cancelled = false

    ;(async () => {
      try {
        const captureOpts = videoDeviceId ? { deviceId: { exact: videoDeviceId } } : undefined
        track = await createLocalVideoTrack(captureOpts)
        if (cancelled) { track.stop(); return }
        await room.localParticipant.publishTrack(track)
        if (!cancelled) setLocalVideoTrack(track)
      } catch (err) {
        if (!cancelled) console.error('webcam publish failed', err)
      }
    })()

    return () => {
      cancelled = true
      if (track) {
        room.localParticipant.unpublishTrack(track).catch(() => {})
        track.stop()
        setLocalVideoTrack(null)
      }
    }
  }, [status, publishWebcam, videoDeviceId])

  return { room: roomRef.current, status, videoTrack, remoteParticipants, localParticipant, localVideoTrack }
}
