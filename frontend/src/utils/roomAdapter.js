import { formatRelative } from './formatDate.js'

export function toRoomCardProps(room) {
  return {
    id: room.id,
    title: room.title,
    host: room.host_name,
    status: room.status,
    viewers: room.num_participants,
    startedAt: startedAtLabel(room),
  }
}

function startedAtLabel(room) {
  if (room.status === 'live') {
    return formatRelative(room.started_at ?? room.created_at)
  }
  if (room.status === 'ended') {
    return `Ended ${formatRelative(room.ended_at)}`
  }
  return `Created ${formatRelative(room.created_at)}`
}
