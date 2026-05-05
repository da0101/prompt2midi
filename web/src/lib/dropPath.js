// Plain utility — no Vue lifecycle involvement.
// Extracts a filesystem path from a Finder drag-and-drop on macOS via text/uri-list.
export function getDropPath(e) {
  const uriList = e.dataTransfer?.getData('text/uri-list')
  if (!uriList) return null
  for (const line of uriList.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('file://')) {
      let raw = trimmed.slice(7)
      if (raw.charCodeAt(raw.length - 1) === 13) raw = raw.slice(0, -1)
      return decodeURIComponent(raw)
    }
  }
  return null
}
