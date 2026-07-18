import { useState } from 'react'
import { Search } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import RoomCard from '../components/RoomCard.jsx'
import { useRooms } from '../hooks/useRooms.js'
import { toRoomCardProps } from '../utils/roomAdapter.js'

export default function Dashboard() {
  const [query, setQuery] = useState('')
  const { rooms, loading, error, refresh } = useRooms()

  const filtered = rooms.filter((r) => {
    const q = query.toLowerCase()
    return r.title.toLowerCase().includes(q) || r.host_name.toLowerCase().includes(q)
  })

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Rooms</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Join a live session or catch up on a past one.
            </p>
          </div>
        </div>

        <div className="relative mt-6 max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search rooms or hosts…"
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
          />
        </div>

        {loading && (
          <p className="mt-16 text-center text-sm text-slate-500 dark:text-slate-400">Loading rooms…</p>
        )}

        {!loading && error && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center">
            <p className="text-sm text-rose-600 dark:text-rose-400">Couldn’t load rooms.</p>
            <button
              onClick={refresh}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <>
            <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((room) => (
                <RoomCard key={room.id} room={toRoomCardProps(room)} />
              ))}
            </div>

            {filtered.length === 0 && (
              <p className="mt-16 text-center text-sm text-slate-500 dark:text-slate-400">
                {rooms.length === 0 ? 'No rooms yet.' : `No rooms match “${query}”.`}
              </p>
            )}
          </>
        )}
      </main>
    </div>
  )
}
