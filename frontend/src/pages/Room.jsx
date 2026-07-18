import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Users } from 'lucide-react'
import VideoPlaceholder from '../components/VideoPlaceholder.jsx'
import LiveVideo from '../components/LiveVideo.jsx'
import AnnotationOverlay from '../components/AnnotationOverlay.jsx'
import AnnotationToolbar from '../components/AnnotationToolbar.jsx'
import ParticipantsList from '../components/ParticipantsList.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useRoomMeta } from '../hooks/useRoomMeta.js'
import { useLiveKitRoom } from '../hooks/useLiveKitRoom.js'
import { useAnnotations } from '../hooks/useAnnotations.js'
import { getViewerToken } from '../api/rooms.js'
import { colorForUser, initialsForName } from '../utils/userColor.js'

export default function Room() {
  const { roomId } = useParams()
  const navigate = useNavigate()
  const { user, isAuthenticated } = useAuth()

  const { room, loading: roomLoading } = useRoomMeta(roomId)

  const [viewerToken, setViewerToken] = useState(null)
  useEffect(() => {
    let cancelled = false
    getViewerToken(roomId, { identity: user?.id, name: user?.name })
      .then((res) => {
        if (!cancelled) setViewerToken(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [roomId, user?.id, user?.name])

  const { room: liveKitRoom, status: connectionStatus, videoTrack, remoteParticipants, localParticipant } =
    useLiveKitRoom({ url: viewerToken?.url, token: viewerToken?.token })

  const localIdentity = localParticipant?.identity

  const [activeTool, setActiveTool] = useState('pen')
  const [showOthers, setShowOthers] = useState(true)
  const [hiddenUserIds, setHiddenUserIds] = useState([])
  const [panelOpen, setPanelOpen] = useState(true)

  const { strokes, handlePointerDown, handlePointerMove, handlePointerUp, undo, clear } = useAnnotations({
    room: liveKitRoom,
    roomId,
    localIdentity,
    activeTool,
  })

  const visibleStrokes = strokes.filter((s) => {
    if (s.userId === localIdentity) return true
    if (!showOthers) return false
    return !hiddenUserIds.includes(s.userId)
  })

  const toggleVisibility = (id) =>
    setHiddenUserIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))

  const participants = useMemo(() => {
    const list = []
    if (localParticipant) {
      const name = user?.name ?? 'You'
      list.push({
        id: localParticipant.identity,
        name: `${name} (You)`,
        initials: initialsForName(name),
        color: colorForUser(localParticipant.identity),
      })
    }
    for (const p of remoteParticipants) {
      list.push({
        id: p.identity,
        name: p.name || p.identity,
        initials: initialsForName(p.name || p.identity),
        color: colorForUser(p.identity),
      })
    }
    return list
  }, [localParticipant, remoteParticipants, user])

  if (!roomLoading && room === null) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-center">
        <p className="text-lg font-semibold text-white">Room not found</p>
        <p className="text-sm text-slate-400">This room doesn’t exist or has been removed.</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
        >
          Back to dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-slate-950">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={() => navigate(isAuthenticated ? '/dashboard' : '/')}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Leave room"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">
              {room?.title ?? (roomLoading ? 'Loading…' : 'Live room')}
            </p>
            <p className="truncate text-xs text-slate-400">Hosted by {room?.host_name ?? 'Unknown host'}</p>
          </div>
          {room?.status === 'live' && (
            <span className="ml-1 hidden shrink-0 items-center gap-1.5 rounded-full bg-rose-600 px-2 py-0.5 text-[11px] font-bold text-white sm:flex">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setPanelOpen((o) => !o)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 sm:text-sm"
          >
            <Users className="h-3.5 w-3.5" /> {participants.length}
          </button>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden p-3 sm:p-4">
        <div className="relative h-full w-full touch-none">
          {videoTrack ? (
            <LiveVideo track={videoTrack} />
          ) : (
            <VideoPlaceholder
              label={
                connectionStatus === 'error'
                  ? 'Could not connect to the stream'
                  : 'Waiting for host to start the stream…'
              }
            />
          )}
          <AnnotationOverlay colorForUser={colorForUser} visible={showOthers} strokes={visibleStrokes} />
          <div
            className="absolute inset-0"
            style={{ pointerEvents: activeTool === 'select' ? 'none' : 'auto', touchAction: 'none' }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          />

          {panelOpen && (
            <div className="absolute right-3 top-3 w-56 sm:right-4 sm:top-4 sm:w-64">
              <ParticipantsList
                participants={participants}
                hiddenUserIds={hiddenUserIds}
                onToggleVisibility={toggleVisibility}
              />
            </div>
          )}

          <AnnotationToolbar
            activeTool={activeTool}
            onSelectTool={setActiveTool}
            onUndo={undo}
            onClear={clear}
            showOthers={showOthers}
            onToggleShowOthers={() => setShowOthers((s) => !s)}
            orientation="vertical"
            className="absolute bottom-4 right-3 sm:right-4"
          />
        </div>
      </div>
    </div>
  )
}
