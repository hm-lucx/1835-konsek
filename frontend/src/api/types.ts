// Shared API types mirroring the backend view-model (Phase 8/9).
// The frontend holds no game logic; every shape here is produced by the server.

export interface HexCoordinate {
  q: number
  r: number
}

export type Terrain =
  | 'plain'
  | 'town'
  | 'city'
  | 'citywhite'
  | 'home'
  | 'citybrown'
  | 'mountain'
  | 'water'
  | 'offboard'

export interface BoardPosition {
  coordinate: HexCoordinate
  tile_id: number
  location_name: string
  terrain: Terrain
  value: string // printed revenue label, e.g. "50" or "20/30/40"
  marker: string // printed glyph: Y / XX / B / H or a company home letter
  stations: { company_id: string }[]
}

export interface BoardState {
  width: number
  height: number
  positions: Record<string, BoardPosition>
}

export interface Tile {
  id: number
  color: 'yellow' | 'green' | 'brown'
  name: string
  cities: number
  value: number
  count: number
  label: string
}

export interface StocksState {
  share_prices: Record<string, number>
  share_price_order: Record<string, string[]> // price → [company_ids] top→bottom
  pool_shares: Record<string, number>
  unsold_shares: Record<string, number>
}

export interface PlayerState {
  player_id: string
  cash: number
  shares: Record<string, number>
  privates: string[]
  paper_count: number
  paper_limit: number
  bankrupt: boolean
}

export interface CompanyState {
  id: string
  name: string
  status: 'inactive' | 'launched' | 'converted' | 'nationalized'
  treasury: number
  trains: { tier: number }[]
  stations: { q: number; r: number }[]
  share_price: number
  director_id: string | null
}

export type GamePhase = 'start_packet_ar' | 'ar' | 'or'
export type ORPhase = 'build' | 'station' | 'run' | 'dividend_decision' | 'buy_train' | 'done'

export interface GameView {
  sequence: number
  game_loop_phase: GamePhase
  phase: GamePhase
  or_phase: ORPhase | null
  colored_phase: 1 | 2 | 3
  active_company_id: string | null
  current_actor: string | null
  game_over: boolean
  bank_balance: number
  train_prices: Record<string, number>
  available_trains: Record<string, number>
  board: BoardState
  tiles: Record<string, Tile>
  stocks: StocksState
  players: PlayerState[]
  companies: CompanyState[]
}

// An action carries its `type` plus inline fields (e.g. { type, item_id }).
export interface Action {
  type: string
  [field: string]: unknown
}

export interface LegalActionsResponse {
  player_id: string
  phase: GamePhase
  or_phase: ORPhase | null
  actions: Action[]
}

export interface LogEntry {
  sequence: number
  type: string
  player_id: string | null
  payload: Record<string, unknown>
}
