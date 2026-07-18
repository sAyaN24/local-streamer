import { Link } from 'react-router-dom'
import { Radio, Users, Clock } from 'lucide-react'

const STATUS_STYLES = {
  live: 'bg-rose-500 text-white',
  scheduled: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  ended: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

const STATUS_LABEL = {
  live: 'LIVE',
  scheduled: 'Scheduled',
  ended: 'Ended',
}

export default function RoomCard({ room }) {
  const isLive = room.status === 'live'

  return (
    <div className="group flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
      <div className="relative flex h-32 items-center justify-center bg-slate-900">
        <Radio className="h-8 w-8 text-slate-600" strokeWidth={1.5} />
        <span
          className={`absolute left-2.5 top-2.5 flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold tracking-wide ${STATUS_STYLES[room.status]}`}
        >
          {isLive && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />}
          {STATUS_LABEL[room.status]}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h3 className="line-clamp-2 font-semibold text-slate-900 dark:text-white">{room.title}</h3>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">Hosted by {room.host}</p>
        </div>

        <div className="mt-auto flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1">
            <Users className="h-3.5 w-3.5" /> {room.viewers}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" /> {room.startedAt}
          </span>
        </div>

        <Link
          to={`/room/${room.id}`}
          aria-disabled={room.status === 'ended'}
          className={`mt-1 rounded-lg px-3 py-2 text-center text-sm font-semibold transition-colors ${
            room.status === 'ended'
              ? 'pointer-events-none bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600'
              : 'bg-brand-500 text-white hover:bg-brand-600'
          }`}
        >
          {isLive ? 'Join stream' : room.status === 'scheduled' ? 'View details' : 'Stream ended'}
        </Link>
      </div>
    </div>
  )
}
