import { useCallback, useEffect, useState } from 'react'
import { listUsers } from '../api/admin.js'

export function useAdminUsers(token) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    return listUsers(token)
      .then((data) => setUsers(data))
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { users, loading, error, refresh }
}
