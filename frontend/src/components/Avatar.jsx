export default function Avatar({ name, initials, color, size = 'md' }) {
  const sizes = {
    sm: 'h-6 w-6 text-[10px]',
    md: 'h-9 w-9 text-xs',
    lg: 'h-11 w-11 text-sm',
  }

  return (
    <div
      title={name}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-white dark:ring-slate-900 ${sizes[size]}`}
      style={{ backgroundColor: color ?? '#64748b' }}
    >
      {initials}
    </div>
  )
}
