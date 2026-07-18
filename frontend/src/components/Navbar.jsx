import { Link, useNavigate } from 'react-router-dom'
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
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo to={isAuthenticated ? '/dashboard' : '/'} />

        <div className="flex items-center gap-2">
          <ThemeToggle />

          {isAuthenticated ? (
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
          ) : (
            <div className="ml-2 flex items-center gap-2">
              <Link
                to="/login"
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Log in
              </Link>
              <Link
                to="/signup"
                className="rounded-lg bg-brand-500 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-600"
              >
                Sign up
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
