import { Link, useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import Logo from './Logo.jsx'
import ThemeToggle from './ThemeToggle.jsx'
import Avatar from './Avatar.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { colorForUser, initialsForName } from '../utils/userColor.js'

export default function Navbar() {
  const navigate = useNavigate()
  const { user, isAuthenticated, logout } = useAuth()

  const handleAvatarClick = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo to={isAuthenticated ? '/dashboard' : '/login'} />

        <div className="flex items-center gap-2">
          <ThemeToggle />

          {isAuthenticated ? (
            <>
              {user.role === 'admin' && (
                <Link
                  to="/admin"
                  title="Admin"
                  className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  <ShieldCheck className="h-4 w-4" />
                  <span className="hidden sm:inline">Admin</span>
                </Link>
              )}
              <button
                onClick={handleAvatarClick}
                title="Log out"
                className="ml-1 flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <Avatar name={user.name} initials={initialsForName(user.name)} color={colorForUser(user.id)} size="sm" />
                <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-200 sm:inline">
                  {user.name}
                </span>
              </button>
            </>
          ) : (
            <div className="ml-2 flex items-center gap-2">
              <Link
                to="/login"
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Log in
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
