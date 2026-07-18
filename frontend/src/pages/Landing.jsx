import { Link } from 'react-router-dom'
import { PenLine, Users2, Radio, ArrowRight } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import VideoPlaceholder from '../components/VideoPlaceholder.jsx'
import AnnotationOverlay from '../components/AnnotationOverlay.jsx'
import { colorForUser } from '../utils/userColor.js'

// Purely illustrative strokes for the marketing preview — not tied to any real room/session.
const PREVIEW_STROKES = [
  {
    strokeId: 'preview-1',
    userId: 'preview-amy',
    tool: 'circle',
    points: [
      { x: 0.2, y: 0.28 },
      { x: 0.36, y: 0.48 },
    ],
  },
  {
    strokeId: 'preview-2',
    userId: 'preview-ravi',
    tool: 'arrow',
    points: [
      { x: 0.48, y: 0.65 },
      { x: 0.62, y: 0.48 },
    ],
  },
  {
    strokeId: 'preview-3',
    userId: 'preview-diego',
    tool: 'text',
    points: [{ x: 0.66, y: 0.3 }],
    text: 'Check this valve',
  },
]

const FEATURES = [
  {
    icon: Radio,
    title: 'Stream any source',
    description: 'Broadcast a live feed to everyone in the room, viewable instantly from any device.',
  },
  {
    icon: PenLine,
    title: 'Annotate in real time',
    description: 'Draw, circle, and point things out directly on the video as it plays.',
  },
  {
    icon: Users2,
    title: 'See everyone’s markup',
    description: 'Every viewer’s annotations show up live, color-coded per person.',
  },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      <Navbar />

      <main className="mx-auto max-w-6xl px-4 pb-24 pt-16 sm:px-6 sm:pt-24">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <span className="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
              Live collaborative streaming
            </span>
            <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-5xl">
              Watch together. <br /> Annotate together.
            </h1>
            <p className="mt-4 max-w-md text-lg text-slate-600 dark:text-slate-400">
              Share a live stream with your team and mark it up together, in real time, on any
              device — mouse, touch, or pen.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/signup"
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-600"
              >
                Get started <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/dashboard"
                className="rounded-lg border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-900"
              >
                Browse live rooms
              </Link>
            </div>
          </div>

          <div className="relative aspect-video w-full">
            <VideoPlaceholder label="Live preview" />
            <AnnotationOverlay colorForUser={colorForUser} strokes={PREVIEW_STROKES} />
          </div>
        </div>

        <div className="mt-24 grid gap-8 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title}>
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-400">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-semibold text-slate-900 dark:text-white">{f.title}</h3>
              <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">{f.description}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
