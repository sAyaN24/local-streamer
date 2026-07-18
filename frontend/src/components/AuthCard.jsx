import Logo from './Logo.jsx'
import ThemeToggle from './ThemeToggle.jsx'

export default function AuthCard({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-950">
      <div className="flex items-center justify-between px-6 py-5">
        <Logo />
        <ThemeToggle />
      </div>

      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-7 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}

          <div className="mt-6">{children}</div>

          {footer && <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">{footer}</p>}
        </div>
      </div>
    </div>
  )
}
