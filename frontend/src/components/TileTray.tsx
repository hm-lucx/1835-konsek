// Shows the tiles available in the current phase (rule 5.5.1.1):
// phase 1 = yellow only, phase 2 = yellow + green, phase 3 = all colours.
import React from 'react'

import type { Tile } from '../api/types'
import { TILE_COLORS } from '../constants'

interface TileTrayProps {
  tiles: Record<string, Tile>
  coloredPhase: 1 | 2 | 3
  selectedTileId: number | null
  onSelectTile: (tileId: number) => void
}

const COLORS_BY_PHASE: Record<number, Tile['color'][]> = {
  1: ['yellow'],
  2: ['yellow', 'green'],
  3: ['yellow', 'green', 'brown'],
}

export function TileTray({
  tiles,
  coloredPhase,
  selectedTileId,
  onSelectTile,
}: TileTrayProps): React.ReactElement {
  const allowed = COLORS_BY_PHASE[coloredPhase] ?? ['yellow']
  const available = Object.values(tiles)
    .filter((tile) => allowed.includes(tile.color))
    .sort((a, b) => a.id - b.id)

  return (
    <div className="tile-tray" data-testid="tile-tray">
      <h2>Gleisplättchen (Phase {coloredPhase})</h2>
      <div className="tile-tray__grid">
        {available.map((tile) => (
          <button
            key={tile.id}
            type="button"
            className={`tile-chip${selectedTileId === tile.id ? ' tile-chip--selected' : ''}`}
            data-testid={`tile-${tile.id}`}
            data-color={tile.color}
            style={{ backgroundColor: TILE_COLORS[tile.color] }}
            onClick={() => onSelectTile(tile.id)}
            title={tile.name}
          >
            #{tile.id}
          </button>
        ))}
      </div>
    </div>
  )
}
