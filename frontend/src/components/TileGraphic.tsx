// Draws a single 18xx tile as SVG: hex fill, track segments, and each stop
// (city circle / town dot) with its revenue and the tile label. Data-driven
// from the parsed tile catalogue — reused in the tile tray and on the board.
import React from 'react'

import { TILE_COLORS } from '../constants'
import { nodePosition, segmentPath, TILE_DEFS, type Vec } from '../tiles/tileGeometry'

interface TileGraphicProps {
  tileId: string | number
  radius: number
  cx?: number
  cy?: number
  rotation?: number // 0-5, in 60° steps
  withFill?: boolean
}

// Flat-top hexagon outline of `radius`, centred at the origin (matches HexMap).
function hexPolygonPoints(radius: number): string {
  const pts: string[] = []
  for (let i = 0; i < 6; i += 1) {
    const a = (Math.PI / 180) * 60 * i
    pts.push(`${radius * Math.cos(a)},${radius * Math.sin(a)}`)
  }
  return pts.join(' ')
}

export function TileGraphic({
  tileId,
  radius,
  cx = 0,
  cy = 0,
  rotation = 0,
  withFill = true,
}: TileGraphicProps): React.ReactElement | null {
  const def = TILE_DEFS[String(tileId)]
  if (!def) return null

  const trackWidth = Math.max(2, radius * 0.16)
  const nodePts: Vec[] = def.nodes.map((n, i) => nodePosition(n, i, def.nodes.length, radius))

  return (
    <g transform={`translate(${cx} ${cy})`}>
      {withFill && (
        <polygon
          points={hexPolygonPoints(radius)}
          fill={TILE_COLORS[def.color]}
          stroke="#6b6b52"
          strokeWidth={0.8}
        />
      )}

      {/* Track + stops rotate together; labels/values stay upright. */}
      <g transform={`rotate(${rotation * 60})`}>
        {def.paths.map((seg, i) => (
          <path
            key={i}
            d={segmentPath(seg, nodePts, radius)}
            fill="none"
            stroke="#1a1a1a"
            strokeWidth={trackWidth}
            strokeLinecap="round"
          />
        ))}

        {def.nodes.map((node, i) =>
          node.kind === 'city' ? (
            <circle
              key={i}
              cx={nodePts[i].x}
              cy={nodePts[i].y}
              r={radius * (node.slots > 1 ? 0.34 : 0.28)}
              fill="#fff"
              stroke="#1a1a1a"
              strokeWidth={trackWidth * 0.55}
            />
          ) : (
            <circle key={i} cx={nodePts[i].x} cy={nodePts[i].y} r={radius * 0.14} fill="#1a1a1a" />
          ),
        )}
      </g>

      {/* Revenue of the first stop (drawn upright, top-left of the hex). */}
      {def.nodes.length > 0 && (
        <text
          x={-radius * 0.5}
          y={-radius * 0.45}
          textAnchor="middle"
          fontSize={radius * 0.3}
          fontWeight={700}
          fill="#1a1a1a"
        >
          {def.nodes[0].revenue}
        </text>
      )}

      {/* Tile label (Y / XX / B / HH …) drawn upright, bottom of the hex. */}
      {def.label && (
        <text
          x={0}
          y={radius * 0.7}
          textAnchor="middle"
          fontSize={radius * 0.3}
          fontWeight={700}
          fill="#1a1a1a"
        >
          {def.label}
        </text>
      )}
    </g>
  )
}
