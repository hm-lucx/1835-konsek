// WebSocket-driven live store (Zustand). The server is the single source of
// truth: on every `state_delta` we refetch the view + legal actions. No
// optimistic updates.
import { create } from 'zustand'

import { getLegalActions, getView, submitAction } from '../api/client'
import type { Action, GameView, LegalActionsResponse } from '../api/types'
import { connectGameSocket } from '../api/websocket'

interface GameStore {
  gameId: number | null
  playerId: string
  view: GameView | null
  legalActions: LegalActionsResponse | null
  socket: WebSocket | null
  error: string | null
  // A rejected/illegal action, shown as a dismissable modal (separate from the
  // connection-level `error` banner).
  actionError: string | null

  connect: (gameId: number, playerId: string) => Promise<void>
  disconnect: () => void
  setError: (error: string | null) => void
  dismissActionError: () => void
  refresh: () => Promise<void>
  submit: (action: Action) => Promise<void>
}

export const useGameStore = create<GameStore>((set, get) => ({
  gameId: null,
  playerId: 'Player 1',
  view: null,
  legalActions: null,
  socket: null,
  error: null,
  actionError: null,

  connect: async (gameId, playerId) => {
    get().disconnect()
    set({ gameId, playerId, error: null })
    await get().refresh()
    const socket = connectGameSocket(gameId, () => {
      void get().refresh()
    })
    set({ socket })
  },

  setError: (error) => set({ error }),

  dismissActionError: () => set({ actionError: null }),

  disconnect: () => {
    const { socket } = get()
    if (socket) {
      socket.close()
      set({ socket: null })
    }
  },

  refresh: async () => {
    const { gameId, playerId } = get()
    if (gameId === null) return
    try {
      const view = await getView(gameId)
      // Solo hot-seat: act as whoever the server says is on turn; turn order is
      // enforced server-side, so legal actions are fetched for that actor.
      const actor = view.current_actor ?? playerId
      const legalActions = await getLegalActions(gameId, actor)
      set({ view, legalActions, error: null })
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) })
    }
  },

  submit: async (action) => {
    const { gameId, playerId, view } = get()
    if (gameId === null || view === null) return
    const actor = view.current_actor ?? playerId
    try {
      await submitAction(gameId, actor, view.sequence, action)
      // The broadcast will trigger refresh(); refresh immediately too so the
      // acting client updates without waiting for the round-trip frame.
      await get().refresh()
    } catch (err) {
      // A rejected move surfaces as a modal explaining why and listing the
      // moves that *are* allowed (refresh keeps `legalActions` current).
      await get().refresh()
      set({ actionError: err instanceof Error ? err.message : String(err) })
    }
  },
}))
