// WebSocket helper. The server pushes a `state_delta` on every accepted action;
// the store reacts by refetching the authoritative view (no optimistic updates).

export interface StateDelta {
  event: 'state_delta'
  sequence: number
  state: Record<string, unknown>
}

export function connectGameSocket(
  gameId: number,
  onDelta: (delta: StateDelta) => void,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  // Vite proxies /ws → backend (see vite.config.ts).
  const url = `${protocol}://${window.location.host}/ws/games/${gameId}`
  const socket = new WebSocket(url)

  socket.onmessage = (event: MessageEvent<string>) => {
    try {
      const message = JSON.parse(event.data) as StateDelta
      if (message.event === 'state_delta') {
        onDelta(message)
      }
    } catch {
      // Ignore malformed frames.
    }
  }
  return socket
}
