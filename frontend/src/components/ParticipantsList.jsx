import { useState } from 'react'
import { ChevronDown, Eye, EyeOff } from 'lucide-react'
import Avatar from './Avatar.jsx'

export default function ParticipantsList({ participants, hiddenUserIds = [], onToggleVisibility }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="w-full overflow-hidden rounded-xl border border-slate-200 bg-white/90 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3.5 py-2.5 text-left"
      >
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Participants · {participants.length}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto scrollbar-thin dark:divide-slate-800">
          {participants.map((p) => {
            const isHidden = hiddenUserIds.includes(p.id)
            return (
              <li key={p.id} className="flex items-center gap-2.5 px-3.5 py-2">
                <Avatar name={p.name} initials={p.initials} color={p.color} size="sm" />
                <span className="flex-1 truncate text-sm text-slate-700 dark:text-slate-200">
                  {p.name}
                </span>
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: p.color }}
                  title="Annotation color"
                />
                {onToggleVisibility && (
                  <button
                    onClick={() => onToggleVisibility(p.id)}
                    className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                    title={isHidden ? 'Show annotations' : 'Hide annotations'}
                  >
                    {isHidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
