import { useCallback, useEffect, useState } from 'react'
import { listRooms } from '../api/rooms.js'

export function useRooms() {
  const [rooms, setRooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    return listRooms()
      .then((data) => setRooms(data))
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { rooms, loading, error, refresh }
}
