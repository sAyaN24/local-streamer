import { Camera, X } from 'lucide-react'

export default function CameraPickerModal({ devices, onSelect, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-brand-400" />
            <h2 className="text-sm font-semibold text-white">Choose video source</h2>
          </div>
          <button
            onClick={onCancel}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <ul className="space-y-2">
          {devices.map((d) => (
            <li key={d.deviceId}>
              <button
                onClick={() => onSelect(d.deviceId)}
                className="w-full rounded-xl border border-slate-700 px-4 py-3 text-left text-sm text-slate-200 hover:border-brand-500 hover:bg-slate-800 hover:text-white"
              >
                {d.label || `Camera ${d.deviceId.slice(0, 8)}`}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
