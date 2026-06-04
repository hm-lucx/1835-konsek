// Renders the 14×10 hex board from the server's axial (q, r) positions.
// Map actions (lay_tile / upgrade_tile / place_station / choose_baden_home_station)
// are performed by clicking a hex while that action is "armed" in the ActionBar.
import React, { useState } from 'react'

import type { GameView } from '../api/types'
import { TILE_COLORS } from '../constants'

const HEX_RADIUS = 26
const H_SPACING = 46
const V_SPACING = 52
const MARGIN = 40

interface HexMapProps {
  view: GameView
  armedMapAction: string | null
  selectedTileId: number | null
  onHexClick: (q: number, r: number) => void
}

function hexCenter(q: number, r: number): { cx: number; cy: number } {
  const cx = MARGIN + q * H_SPACING
  const cy = MARGIN + r * V_SPACING + (q % 2) * (V_SPACING / 2)
  return { cx, cy }
}

function hexPoints(cx: number, cy: number): string {
  const points: string[] = []
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30)
    points.push(`${cx + HEX_RADIUS * Math.cos(angle)},${cy + HEX_RADIUS * Math.sin(angle)}`)
  }
  return points.join(' ')
}

export function HexMap({
  view,
  armedMapAction,
  selectedTileId,
  onHexClick,
}: HexMapProps): React.ReactElement {
  const [hovered, setHovered] = useState<string | null>(null)
  const positions = Object.entries(view.board.positions)

  const maxQ = Math.max(...positions.map(([, p]) => p.coordinate.q))
  const maxR = Math.max(...positions.map(([, p]) => p.coordinate.r))
  const svgWidth = MARGIN * 2 + maxQ * H_SPACING
  const svgHeight = MARGIN * 2 + maxR * V_SPACING + V_SPACING

  const previewColor = selectedTileId
    ? TILE_COLORS[view.tiles[String(selectedTileId)]?.color ?? 'yellow']
    : TILE_COLORS.green

  return (
    <svg
      className="hex-map"
      data-testid="hex-map"
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      role="img"
      aria-label="Spielbrett"
    >
      {positions.map(([key, pos]) => {
        const { cx, cy } = hexCenter(pos.coordinate.q, pos.coordinate.r)
        const tile = view.tiles[String(pos.tile_id)]
        const fill = tile ? TILE_COLORS[tile.color] : '#e8e8e8'
        const isHovered = hovered === key
        const clickable = armedMapAction !== null
        return (
          <g
            key={key}
            data-testid={`hex-${key}`}
            data-tile-color={tile?.color ?? 'none'}
            className={clickable ? 'hex hex--clickable' : 'hex'}
            onMouseEnter={() => setHovered(key)}
            onMouseLeave={() => setHovered((h) => (h === key ? null : h))}
            onClick={() => clickable && onHexClick(pos.coordinate.q, pos.coordinate.r)}
          >
            <polygon
              points={hexPoints(cx, cy)}
              fill={clickable && isHovered ? previewColor : fill}
              fillOpacity={clickable && isHovered ? 0.55 : 1}
              stroke="#333"
              strokeWidth={clickable && isHovered ? 2.5 : 1}
            />
            <text x={cx} y={cy + 3} textAnchor="middle" className="hex-label">
              {pos.location_name}
            </text>
            {pos.stations.map((s, i) => (
              <circle
                key={s.company_id}
                cx={cx - 10 + i * 8}
                cy={cy + 12}
                r={4}
                fill="#1a1a1a"
              />
            ))}
          </g>
        )
      })}
    </svg>
  )
}
