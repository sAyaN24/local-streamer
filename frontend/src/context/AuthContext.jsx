import { createContext, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth.js'
import { ApiError } from '../api/client.js'

const AuthContext = createContext(null)
const STORAGE_KEY = 'streammark.auth'

function getInitialAuth() {
  if (typeof window === 'undefined') return { user: null, token: null }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return { user: null, token: null }
    const parsed = JSON.parse(stored)
    return { user: parsed.user ?? null, token: parsed.token ?? null }
  } catch {
    return { user: null, token: null }
  }
}

export function AuthProvider({ children }) {
  const [{ user, token }, setAuth] = useState(getInitialAuth)
  const [checkingSession, setCheckingSession] = useState(() => !!getInitialAuth().token)

  useEffect(() => {
    if (user && token) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, token }))
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }, [user, token])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    authApi
      .getMe(token)
      .then((freshUser) => {
        if (!cancelled) setAuth({ user: freshUser, token })
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          setAuth({ user: null, token: null })
        }
      })
      .finally(() => {
        if (!cancelled) setCheckingSession(false)
      })
    return () => {
      cancelled = true
    }
    // Only run once on mount against whatever token was loaded from storage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = async (email, password) => {
    const res = await authApi.login({ email, password })
    setAuth({ user: res.user, token: res.token })
    return res.user
  }

  const signup = async (email, password, name) => {
    const res = await authApi.signup({ email, password, name })
    setAuth({ user: res.user, token: res.token })
    return res.user
  }

  const logout = () => {
    setAuth({ user: null, token: null })
  }

  const value = {
    user,
    token,
    isAuthenticated: !!token,
    checkingSession,
    login,
    signup,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
