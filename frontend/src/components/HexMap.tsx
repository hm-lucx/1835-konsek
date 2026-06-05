// Renders the printed 1835 board from the server's (q, r) hex positions.
// Flat-top hexes, odd-q offset down half a row — matching the printed map.
// Each hex is coloured by its terrain; cities/towns/mountains/off-board regions
// carry their printed station, glyph (Y/XX/B/H/home letter) and revenue value.
// A placed rail tile (tile_id > 0) overrides the base colour (rule 5.5.1).
import React, { useState } from 'react'

import type { BoardPosition, GameView, Terrain } from '../api/types'
import { TILE_COLORS } from '../constants'

const HEX_RADIUS = 26
const H_SPACING = 39 // 1.5 * radius for flat-top columns
const V_SPACING = 45 // sqrt(3) * radius
const MARGIN = 34

// Terrain fill colours approximating the printed board.
const TERRAIN_FILL: Record<Terrain, string> = {
  plain: '#d8d2a0',
  town: '#d8d2a0',
  city: '#f4d23f', // pre-printed yellow city tile
  citywhite: '#d8d2a0', // white station on open land
  home: '#d8d2a0', // grey home marker drawn on top
  citybrown: '#a9601f',
  mountain: '#cdc592',
  water: '#79b0d6',
  offboard: '#b34a35',
}

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
    const angle = (Math.PI / 180) * 60 * i
    points.push(`${cx + HEX_RADIUS * Math.cos(angle)},${cy + HEX_RADIUS * Math.sin(angle)}`)
  }
  return points.join(' ')
}

// The station glyph drawn for a city/home hex.
function StationGlyph({
  terrain,
  marker,
  cx,
  cy,
}: {
  terrain: Terrain
  marker: string
  cx: number
  cy: number
}): React.ReactElement | null {
  if (terrain === 'city' || terrain === 'citywhite') {
    return <circle cx={cx} cy={cy} r={7} fill="#fff" stroke="#222" strokeWidth={1.2} />
  }
  if (terrain === 'home') {
    return <circle cx={cx} cy={cy} r={8} fill="#8c8c8c" stroke="#222" strokeWidth={1.2} />
  }
  if (terrain === 'citybrown') {
    return <circle cx={cx} cy={cy} r={7} fill="#e8dcc0" stroke="#222" strokeWidth={1.2} />
  }
  if (terrain === 'town') {
    return <circle cx={cx} cy={cy} r={3} fill="#222" />
  }
  void marker
  return null
}

function fillFor(pos: BoardPosition, view: GameView): string {
  const placed = view.tiles[String(pos.tile_id)]
  if (pos.tile_id > 0 && placed) return TILE_COLORS[placed.color] ?? TERRAIN_FILL.plain
  return TERRAIN_FILL[pos.terrain] ?? TERRAIN_FILL.plain
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
      {/* Sea / outside-Germany background. */}
      <rect x={0} y={0} width={svgWidth} height={svgHeight} fill="#5f8b46" />

      {positions.map(([key, pos]) => {
        const { cx, cy } = hexCenter(pos.coordinate.q, pos.coordinate.r)
        const fill = fillFor(pos, view)
        const isHovered = hovered === key
        const clickable = armedMapAction !== null
        return (
          <g
            key={key}
            data-testid={`hex-${key}`}
            data-terrain={pos.terrain}
            className={clickable ? 'hex hex--clickable' : 'hex'}
            onMouseEnter={() => setHovered(key)}
            onMouseLeave={() => setHovered((h) => (h === key ? null : h))}
            onClick={() => clickable && onHexClick(pos.coordinate.q, pos.coordinate.r)}
          >
            <polygon
              points={hexPoints(cx, cy)}
              fill={clickable && isHovered ? previewColor : fill}
              fillOpacity={clickable && isHovered ? 0.7 : 1}
              stroke="#6b6b52"
              strokeWidth={clickable && isHovered ? 2.5 : 0.8}
            />

            {/* Mountain build-cost triangle. */}
            {pos.terrain === 'mountain' && (
              <polygon
                points={`${cx - 6},${cy + 4} ${cx + 6},${cy + 4} ${cx},${cy - 7}`}
                fill="none"
                stroke="#6b5b32"
                strokeWidth={1.3}
              />
            )}

            <StationGlyph terrain={pos.terrain} marker={pos.marker} cx={cx} cy={cy} />

            {/* Printed company/city glyph (Y / XX / B / H / home letter). */}
            {pos.marker && (
              <text
                x={cx}
                y={cy + 2.6}
                textAnchor="middle"
                className="hex-marker"
                fill={pos.terrain === 'home' ? '#fff' : '#11181f'}
              >
                {pos.marker}
              </text>
            )}

            {/* Revenue value (cities, mountains, off-board). */}
            {pos.value && (
              <text x={cx} y={cy - 11} textAnchor="middle" className="hex-value">
                {pos.value}
              </text>
            )}

            {/* Location name beneath the hex. */}
            {pos.location_name && (
              <text x={cx} y={cy + 17} textAnchor="middle" className="hex-label">
                {pos.location_name}
              </text>
            )}

            {/* Placed station markers (operating companies). */}
            {pos.stations.map((s, i) => (
              <circle key={s.company_id} cx={cx - 9 + i * 8} cy={cy + 10} r={3.5} fill="#1a1a1a" />
            ))}
          </g>
        )
      })}
    </svg>
  )
}
