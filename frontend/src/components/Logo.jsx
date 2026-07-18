import { Radio } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Logo({ to = '/' }) {
  return (
    <Link to={to} className="flex items-center gap-2 text-slate-900 dark:text-white">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500 text-white">
        <Radio className="h-5 w-5" strokeWidth={2.2} />
      </span>
      <span className="text-lg font-bold tracking-tight">StreamMark</span>
    </Link>
  )
}
