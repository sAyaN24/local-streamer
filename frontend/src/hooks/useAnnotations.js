import { useCallback, useEffect, useRef, useState } from 'react'
import { RoomEvent } from 'livekit-client'
import { colorForUser } from '../utils/userColor.js'
import { getAnnotationHistory } from '../api/rooms.js'
import { toRelative } from '../utils/pupilRelative.js'

// Peer-to-peer annotation protocol over LiveKit's data channel. There is no backend spec for
// this — the wire format below is a frontend invention (see integration plan §5d). Messages are
// JSON, UTF-8 encoded, published with LiveKit's `topic` set to ANNOTATION_TOPIC so non-annotation
// data messages can be filtered without a JSON parse.
//
// Stroke `points` are stored pupil-relative (see utils/pupilRelative.js), not as raw
// frame-normalized coordinates: each point is captured as an offset from the pupil's
// center/radius *at the moment it was drawn*. Rendering (AnnotationOverlay) resolves
// these back to absolute coordinates against the *current* pupil reading, which is what
// makes annotations track the pupil live as it moves/resizes, including for strokes
// replayed from history against a pupil position the drawer never saw.
const ANNOTATION_TOPIC = 'annotation'
const encoder = new TextEncoder()
const decoder = new TextDecoder()

function newStrokeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `stroke-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function clamp01(n) {
  return Math.min(1, Math.max(0, n))
}

function normalizedPoint(container, clientX, clientY) {
  const rect = container.getBoundingClientRect()
  return {
    x: clamp01((clientX - rect.left) / rect.width),
    y: clamp01((clientY - rect.top) / rect.height),
  }
}

export function useAnnotations({ room, roomId, localIdentity, activeTool, pupil }) {
  const [strokes, setStrokes] = useState([])
  const drawingRef = useRef(null)
  // Read via ref (not the `pupil` value directly) inside the pointer callbacks so a
  // per-frame pupil update doesn't recreate handlePointerDown/Move/Up on every tick --
  // they're still always evaluated against the latest reading.
  const pupilRef = useRef(pupil)
  useEffect(() => {
    pupilRef.current = pupil
  }, [pupil])

  const publish = useCallback(
    (message) => {
      if (!room) return
      room.localParticipant.publishData(encoder.encode(JSON.stringify(message)), {
        reliable: true,
        topic: ANNOTATION_TOPIC,
      })
    },
    [room],
  )

  const applyMessage = useCallback((message) => {
    setStrokes((current) => {
      if (message.type === 'draw') {
        return [...current.filter((s) => s.strokeId !== message.strokeId), message]
      }
      if (message.type === 'undo') {
        return current.filter((s) => s.strokeId !== message.strokeId)
      }
      if (message.type === 'clear') {
        return current.filter((s) => s.userId !== message.userId)
      }
      return current
    })
  }, [])

  // Backend-persisted catch-up: replays the room's annotation history (recorded by
  // tools/logger_bot.py off the data channel) so late joiners see strokes drawn before they
  // connected, not just ones drawn live afterward. Independent of the LiveKit connection —
  // plain REST, so it loads even before/without a successful room.connect().
  useEffect(() => {
    if (!roomId) return
    let cancelled = false
    getAnnotationHistory(roomId)
      .then((events) => {
        if (cancelled) return
        for (const event of events) applyMessage(event.payload)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [roomId, applyMessage])

  useEffect(() => {
    if (!room) return
    const handleData = (payload, _participant, _kind, topic) => {
      if (topic !== ANNOTATION_TOPIC) return
      let message
      try {
        message = JSON.parse(decoder.decode(payload))
      } catch {
        return
      }
      applyMessage(message)
    }
    room.on(RoomEvent.DataReceived, handleData)
    return () => room.off(RoomEvent.DataReceived, handleData)
  }, [room, applyMessage])

  const handlePointerDown = useCallback(
    (e) => {
      if (activeTool === 'select' || !localIdentity) return
      const container = e.currentTarget
      const point = toRelative(normalizedPoint(container, e.clientX, e.clientY), pupilRef.current)

      if (activeTool === 'text') {
        const text = window.prompt('Annotation text')
        if (!text) return
        const message = {
          type: 'draw',
          userId: localIdentity,
          strokeId: newStrokeId(),
          tool: 'text',
          color: colorForUser(localIdentity),
          points: [point],
          text,
          ts: Date.now(),
        }
        applyMessage(message)
        publish(message)
        return
      }

      container.setPointerCapture?.(e.pointerId)
      drawingRef.current = {
        strokeId: newStrokeId(),
        tool: activeTool,
        color: colorForUser(localIdentity),
        points: [point],
      }
    },
    [activeTool, localIdentity, applyMessage, publish],
  )

  const handlePointerMove = useCallback(
    (e) => {
      const drawing = drawingRef.current
      if (!drawing) return
      const point = toRelative(normalizedPoint(e.currentTarget, e.clientX, e.clientY), pupilRef.current)
      drawing.points = drawing.tool === 'pen' ? [...drawing.points, point] : [drawing.points[0], point]

      setStrokes((current) => [
        ...current.filter((s) => s.strokeId !== drawing.strokeId),
        { type: 'draw', userId: localIdentity, ...drawing },
      ])
    },
    [localIdentity],
  )

  const handlePointerUp = useCallback(
    (e) => {
      const drawing = drawingRef.current
      drawingRef.current = null
      if (!drawing || drawing.points.length === 0) return
      e.currentTarget.releasePointerCapture?.(e.pointerId)

      const message = {
        type: 'draw',
        userId: localIdentity,
        strokeId: drawing.strokeId,
        tool: drawing.tool,
        color: drawing.color,
        points: drawing.points,
        ts: Date.now(),
      }
      applyMessage(message)
      publish(message)
    },
    [localIdentity, applyMessage, publish],
  )

  const undo = useCallback(() => {
    const mine = strokes.filter((s) => s.userId === localIdentity)
    const last = mine[mine.length - 1]
    if (!last) return
    const message = { type: 'undo', userId: localIdentity, strokeId: last.strokeId, ts: Date.now() }
    applyMessage(message)
    publish(message)
  }, [strokes, localIdentity, applyMessage, publish])

  const clear = useCallback(() => {
    const message = { type: 'clear', userId: localIdentity, ts: Date.now() }
    applyMessage(message)
    publish(message)
  }, [localIdentity, applyMessage, publish])

  return { strokes, handlePointerDown, handlePointerMove, handlePointerUp, undo, clear }
}
