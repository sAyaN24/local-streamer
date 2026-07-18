export const USER_COLORS = [
  '#f43f5e', // rose
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // amber
  '#a855f7', // purple
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#84cc16', // lime
]

export function colorForUser(userId) {
  if (!userId) return USER_COLORS[0]
  const index = Math.abs(hashString(userId)) % USER_COLORS.length
  return USER_COLORS[index]
}

function hashString(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i)
    hash |= 0
  }
  return hash
}

export function initialsForName(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  const initials = parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]
  return initials.toUpperCase()
}
