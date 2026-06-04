// Reference data shared by several components. These mirror the rulebook /
// backend tables; they are display constants only (no logic).

// Aktienkurstafel track, ascending (rule 2.6.3).
export const SHARE_PRICE_TRACK: readonly number[] = [
  50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 135, 150, 165, 180, 200, 220, 245, 270, 300, 330,
  365, 400,
]

// Locomotive list prices (rule Promotionstabellen) – also delivered by the
// server in GameView.train_prices; kept here for the fixed column order.
export const TRAIN_ORDER: readonly string[] = [
  '2',
  '2+2',
  '3',
  '3+3',
  '4',
  '4+4',
  '5',
  '5+5',
  '6',
  '6+6',
]

// Legacy integer tier → canonical train id (matches backend fsm.TIER_TRAIN).
export const TIER_TO_TRAIN: Record<number, string> = {
  1: '2',
  2: '3',
  3: '4',
  4: '5',
  5: '6',
  6: '6+6',
  7: '2+2',
  8: '3+3',
  9: '4+4',
  10: '5+5',
}

export const TILE_COLORS: Record<string, string> = {
  yellow: '#f4d03f',
  green: '#58d68d',
  brown: '#a04000',
}
