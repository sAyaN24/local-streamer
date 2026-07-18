import {
  MousePointer2,
  Pencil,
  Square,
  Circle,
  ArrowUpRight,
  Type,
  Undo2,
  Trash2,
  Eye,
  EyeOff,
} from 'lucide-react'

const TOOLS = [
  { id: 'select', label: 'Select', icon: MousePointer2 },
  { id: 'pen', label: 'Pen', icon: Pencil },
  { id: 'rectangle', label: 'Rectangle', icon: Square },
  { id: 'circle', label: 'Circle', icon: Circle },
  { id: 'arrow', label: 'Arrow', icon: ArrowUpRight },
  { id: 'text', label: 'Text', icon: Type },
]

export default function AnnotationToolbar({
  activeTool,
  onSelectTool,
  onUndo,
  onClear,
  showOthers = true,
  onToggleShowOthers,
  orientation = 'vertical',
  className = '',
}) {
  const isVertical = orientation === 'vertical'

  return (
    <div
      className={`flex ${isVertical ? 'flex-col' : 'flex-row'} items-center gap-1 rounded-2xl border border-slate-200 bg-white/95 p-1.5 shadow-lg backdrop-blur dark:border-slate-800 dark:bg-slate-900/95 ${className}`}
    >
      {TOOLS.map((tool) => {
        const Icon = tool.icon
        const isActive = activeTool === tool.id
        return (
          <button
            key={tool.id}
            onClick={() => onSelectTool?.(tool.id)}
            title={tool.label}
            aria-label={tool.label}
            aria-pressed={isActive}
            className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors touch-manipulation ${
              isActive
                ? 'bg-brand-500 text-white shadow-sm'
                : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            }`}
          >
            <Icon className="h-5 w-5" strokeWidth={2} />
          </button>
        )
      })}

      <div className={isVertical ? 'my-1 h-px w-8 bg-slate-200 dark:bg-slate-800' : 'mx-1 h-8 w-px bg-slate-200 dark:bg-slate-800'} />

      <button
        onClick={onUndo}
        title="Undo last annotation"
        aria-label="Undo"
        className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
      >
        <Undo2 className="h-5 w-5" />
      </button>

      <button
        onClick={onClear}
        title="Clear all annotations"
        aria-label="Clear all"
        className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-600 dark:text-slate-400 dark:hover:bg-rose-950/50 dark:hover:text-rose-400"
      >
        <Trash2 className="h-5 w-5" />
      </button>

      <div className={isVertical ? 'my-1 h-px w-8 bg-slate-200 dark:bg-slate-800' : 'mx-1 h-8 w-px bg-slate-200 dark:bg-slate-800'} />

      <button
        onClick={onToggleShowOthers}
        title={showOthers ? "Hide others' annotations" : "Show others' annotations"}
        aria-label="Toggle other annotations"
        aria-pressed={showOthers}
        className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
          showOthers
            ? 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
        }`}
      >
        {showOthers ? <Eye className="h-5 w-5" /> : <EyeOff className="h-5 w-5" />}
      </button>
    </div>
  )
}
