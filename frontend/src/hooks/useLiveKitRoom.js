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

    // Backstop for a known livekit-client desync ("Tried to add a track for a
    // participant, that's not present") where an already-published remote video
    // track's TrackSubscribed event never reaches this listener, leaving
    // videoTrack stuck at null even though the server has the track live. Scans
    // every remote participant's video publications directly: adopts one that's
    // already subscribed, and explicitly (re)requests subscription for one that
    // isn't -- autoSubscribe should have covered that, but this makes it
    // self-healing instead of depending on a single event firing correctly.
    const reconcileVideoTrack = () => {
      for (const participant of room.remoteParticipants.values()) {
        for (const publication of participant.videoTrackPublications.values()) {
          if (publication.track) {
            setVideoTrack(publication.track)
            return
          }
          if (!publication.isSubscribed) publication.setSubscribed(true)
        }
      }
    }

    room.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === Track.Kind.Video) setVideoTrack(track)
    })
    room.on(RoomEvent.TrackUnsubscribed, (track) => {
      if (track.kind === Track.Kind.Video) {
        setVideoTrack((current) => (current === track ? null : current))
      }
    })
    room.on(RoomEvent.TrackPublished, reconcileVideoTrack)
    room.on(RoomEvent.ParticipantConnected, () => {
      syncParticipants()
      reconcileVideoTrack()
    })
    room.on(RoomEvent.ParticipantDisconnected, syncParticipants)
    room.on(RoomEvent.Disconnected, () => {
      if (!cancelled) setStatus('disconnected')
    })

    const connectPromise = room
      .connect(url, token)
      .then(() => {
        if (cancelled) return
        setStatus('connected')
        setLocalParticipant(room.localParticipant)
        syncParticipants()
        reconcileVideoTrack()
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })

    return () => {
      cancelled = true
      // Wait for the in-flight connect() to settle before disconnecting. Under
      // React StrictMode, this cleanup runs immediately after mount (mount ->
      // cleanup -> mount) while connect() is still pending; disconnecting mid
      // handshake races the reconnect that follows, and since both use the
      // same participant identity, the server briefly holds two overlapping
      // sessions under it -- the client then gets track events for a
      // participant SID it no longer recognizes ("Tried to add a track for a
      // participant, that's not present") and the room stays broken.
      connectPromise.finally(() => room.disconnect())
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
