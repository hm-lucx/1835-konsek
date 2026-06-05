// Shows the tiles available in the current phase (rule 5.5.1.1):
// phase 1 = yellow only, phase 2 = yellow + green, phase 3 = all colours.
// Tiles are drawn from the real 18xx 1835 catalogue with their track geometry
// and supply counts.
import React from 'react'

import type { Tile } from '../api/types'
import { type TileColor, tilesByColor } from '../tiles/tileGeometry'
import { TileGraphic } from './TileGraphic'

interface TileTrayProps {
  tiles: Record<string, Tile>
  coloredPhase: 1 | 2 | 3
  selectedTileId: number | null
  onSelectTile: (tileId: number) => void
}

const COLORS_BY_PHASE: Record<number, TileColor[]> = {
  1: ['yellow'],
  2: ['yellow', 'green'],
  3: ['yellow', 'green', 'brown'],
}

const COLOR_LABEL: Record<TileColor, string> = {
  yellow: 'Gelb',
  green: 'Grün',
  brown: 'Braun',
}

export function TileTray({
  coloredPhase,
  selectedTileId,
  onSelectTile,
}: TileTrayProps): React.ReactElement {
  const allowed = COLORS_BY_PHASE[coloredPhase] ?? ['yellow']

  return (
    <div className="tile-tray" data-testid="tile-tray">
      <h2>Gleisplättchen (Phase {coloredPhase})</h2>

      {allowed.map((color) => (
        <div key={color} className="tile-tray__group" data-testid={`tile-group-${color}`}>
          <h3>{COLOR_LABEL[color]}</h3>
          <div className="tile-tray__grid">
            {tilesByColor(color).map((def) => {
              const id = Number(def.id)
              return (
                <button
                  key={def.id}
                  type="button"
                  className={`tile-chip tile-chip--graphic${
                    selectedTileId === id ? ' tile-chip--selected' : ''
                  }`}
                  data-testid={`tile-${def.id}`}
                  data-color={def.color}
                  onClick={() => onSelectTile(id)}
                  title={`Tile #${def.id}${def.label ? ` (${def.label})` : ''} — ${def.count}×`}
                >
                  <svg viewBox="-30 -30 60 60" className="tile-chip__svg" aria-label={`Tile ${def.id}`}>
                    <TileGraphic tileId={def.id} radius={28} />
                  </svg>
                  <span className="tile-chip__id">
                    #{def.id} <span className="tile-chip__count">×{def.count}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
