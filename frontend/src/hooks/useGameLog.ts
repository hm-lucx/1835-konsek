// TanStack Query hook for the (append-only) game log. Refetches when the live
// sequence advances so the log stays in sync with the WebSocket-driven view.
import { useQuery } from '@tanstack/react-query'

import { getLog } from '../api/client'
import type { LogEntry } from '../api/types'

export function useGameLog(gameId: number | null, sequence: number): {
  events: LogEntry[]
  isLoading: boolean
} {
  const query = useQuery({
    queryKey: ['log', gameId, sequence],
    queryFn: () => getLog(gameId as number),
    enabled: gameId !== null,
  })
  return { events: query.data?.events ?? [], isLoading: query.isLoading }
}
