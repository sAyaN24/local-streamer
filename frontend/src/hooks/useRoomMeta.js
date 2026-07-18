import { useEffect, useState } from 'react'
import { listRooms } from '../api/rooms.js'

export function useRoomMeta(roomId) {
  const [room, setRoom] = useState(undefined)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setRoom(undefined)

    listRooms()
      .then((rooms) => {
        if (cancelled) return
        setRoom(rooms.find((r) => r.id === roomId) ?? null)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [roomId])

  return { room, loading, error }
}
