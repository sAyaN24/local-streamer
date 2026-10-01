import { useState } from 'react'
import { ShieldCheck, UserPlus } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import Avatar from '../components/Avatar.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useAdminUsers } from '../hooks/useAdminUsers.js'
import { createUser } from '../api/admin.js'
import { ApiError } from '../api/client.js'
import { formatAbsolute } from '../utils/formatDate.js'
import { colorForUser, initialsForName } from '../utils/userColor.js'

export default function Admin() {
  const { token } = useAuth()
  const { users, loading, error, refresh } = useAdminUsers(token)

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />

      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-brand-600 dark:text-brand-400" />
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Admin</h1>
        </div>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Add accounts for the people who should be able to log in.
        </p>

        <AddUserForm onCreated={refresh} />

        <h2 className="mt-10 text-sm font-semibold text-slate-700 dark:text-slate-300">
          Users
        </h2>

        {loading && (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Loading users…</p>
        )}

        {!loading && error && (
          <div className="mt-4 flex items-center gap-3">
            <p className="text-sm text-rose-600 dark:text-rose-400">Couldn’t load users.</p>
            <button
              onClick={refresh}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <ul className="mt-4 divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
            {users.map((u) => (
              <li key={u.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar name={u.name} initials={initialsForName(u.name)} color={colorForUser(u.id)} size="sm" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{u.name}</p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">{u.email}</p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    {formatAbsolute(u.created_at)}
                  </span>
                  {u.role === 'admin' && (
                    <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                      Admin
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}

function AddUserForm({ onCreated }) {
  const { token } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('user')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSubmitting(true)
    try {
      const created = await createUser({ email, password, name, role }, token)
      setSuccess(`Added ${created.name} (${created.email}).`)
      setName('')
      setEmail('')
      setPassword('')
      setRole('user')
      onCreated()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('An account with this email already exists.')
      } else if (err instanceof ApiError) {
        setError(err.detail || 'Something went wrong. Please try again.')
      } else {
        setError('Could not reach the server. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-center gap-2">
        <UserPlus className="h-4 w-4 text-slate-500 dark:text-slate-400" />
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Add a user</h2>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field
          label="Full name"
          type="text"
          placeholder="Jane Doe"
          required
          minLength={1}
          maxLength={128}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Field
          label="Email"
          type="email"
          placeholder="jane@example.com"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          label="Password"
          type="password"
          placeholder="••••••••"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-slate-700 dark:text-slate-300">Role</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      {success && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{success}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="mt-4 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Adding…' : 'Add user'}
      </button>
    </form>
  )
}

function Field({ label, ...props }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <input
        {...props}
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
      />
    </label>
  )
}
