// REST client. All game logic lives on the server; this only (de)serialises.
import type { Action, GameView, LegalActionsResponse, LogEntry } from './types'

// Vite proxies /api → backend (see vite.config.ts).
const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    // FastAPI errors come back as {"detail": "..."}; unwrap it for a clean
    // human-readable message (falls back to the raw body).
    const body = await response.text()
    let detail = body
    try {
      const parsed = JSON.parse(body) as { detail?: unknown }
      if (typeof parsed.detail === 'string') detail = parsed.detail
    } catch {
      /* not JSON — keep the raw body */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function createGame(numPlayers: number, creatorEmail?: string): Promise<number> {
  const body = await request<{ game_id: number }>('/games', {
    method: 'POST',
    body: JSON.stringify({ num_players: numPlayers, creator_email: creatorEmail ?? null }),
  })
  return body.game_id
}

export function getView(gameId: number): Promise<GameView> {
  return request<GameView>(`/games/${gameId}/view`)
}

export function getLegalActions(gameId: number, playerId: string): Promise<LegalActionsResponse> {
  const params = new URLSearchParams({ player_id: playerId })
  return request<LegalActionsResponse>(`/games/${gameId}/legal_actions?${params}`)
}

export function getLog(gameId: number): Promise<{ events: LogEntry[] }> {
  return request<{ events: LogEntry[] }>(`/games/${gameId}/log`)
}

// Submit an action. The server validates; we wrap the inline action fields into
// the {type, payload} envelope and attach player_id + expected_seq.
export async function submitAction(
  gameId: number,
  playerId: string,
  expectedSeq: number,
  action: Action,
): Promise<{ sequence: number }> {
  const { type, ...fields } = action
  return request<{ sequence: number }>(`/games/${gameId}/actions`, {
    method: 'POST',
    body: JSON.stringify({
      player_id: playerId,
      expected_seq: expectedSeq,
      type,
      payload: { player_id: playerId, ...fields },
    }),
  })
}
