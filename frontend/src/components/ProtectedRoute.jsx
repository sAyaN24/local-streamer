import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, checkingSession } = useAuth()

  if (checkingSession) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return children
}
