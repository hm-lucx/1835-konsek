// The complete 1835 tile catalogue, with real track geometry.
//
// Tile codes are taken verbatim from the 18xx engine (tobymao/18xx,
// lib/engine/config/tile.rb) — the same definitions 18xx.games uses — and the
// supply counts from its 1835 map (lib/engine/game/g_1835/map.rb). We parse the
// `path=a:A,b:B` notation at load time into nodes + track segments.
//
// Edge numbering on a flat-top hex, clockwise from the top edge:
//   0 = N, 1 = NE, 2 = SE, 3 = S, 4 = SW, 5 = NW
// An endpoint `a:_N` refers to the N-th city/town defined on that tile.
// (The catalogue's absolute orientation may differ from the printed art by a
// fixed rotation; the track *shape* and connections are identical.)

export type TileColor = 'yellow' | 'green' | 'brown'
export type NodeKind = 'city' | 'town'

// One raw catalogue entry: colour, supply count, and the verbatim 18xx code.
interface RawTile {
  color: TileColor
  count: number
  code: string
}

// --- 1835 tile catalogue (verbatim codes + counts) ------------------------
export const RAW_TILES: Record<string, RawTile> = {
  // Yellow
  '1': { color: 'yellow', count: 1, code: 'town=revenue:10;town=revenue:10;path=a:1,b:_0;path=a:_0,b:3;path=a:0,b:_1;path=a:_1,b:4' },
  '2': { color: 'yellow', count: 1, code: 'town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:1,b:_1;path=a:_1,b:2' },
  '3': { color: 'yellow', count: 2, code: 'town=revenue:10;path=a:0,b:_0;path=a:_0,b:1' },
  '4': { color: 'yellow', count: 3, code: 'town=revenue:10;path=a:0,b:_0;path=a:_0,b:3' },
  '5': { color: 'yellow', count: 3, code: 'city=revenue:20;path=a:0,b:_0;path=a:1,b:_0' },
  '6': { color: 'yellow', count: 3, code: 'city=revenue:20;path=a:0,b:_0;path=a:2,b:_0' },
  '7': { color: 'yellow', count: 8, code: 'path=a:0,b:1' },
  '8': { color: 'yellow', count: 16, code: 'path=a:0,b:2' },
  '9': { color: 'yellow', count: 12, code: 'path=a:0,b:3' },
  '55': { color: 'yellow', count: 1, code: 'town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:1,b:_1;path=a:_1,b:4' },
  '56': { color: 'yellow', count: 1, code: 'town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:2;path=a:1,b:_1;path=a:_1,b:3' },
  '57': { color: 'yellow', count: 2, code: 'city=revenue:20;path=a:0,b:_0;path=a:_0,b:3' },
  '58': { color: 'yellow', count: 4, code: 'town=revenue:10;path=a:0,b:_0;path=a:_0,b:2' },
  '69': { color: 'yellow', count: 2, code: 'town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:2,b:_1;path=a:_1,b:4' },
  '201': { color: 'yellow', count: 2, code: 'city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;label=Y' },
  '202': { color: 'yellow', count: 2, code: 'city=revenue:30;path=a:0,b:_0;path=a:2,b:_0;label=Y' },
  // Green
  '12': { color: 'green', count: 2, code: 'city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0' },
  '13': { color: 'green', count: 2, code: 'city=revenue:30;path=a:0,b:_0;path=a:2,b:_0;path=a:4,b:_0' },
  '14': { color: 'green', count: 2, code: 'city=revenue:30,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0' },
  '15': { color: 'green', count: 2, code: 'city=revenue:30,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0' },
  '16': { color: 'green', count: 2, code: 'path=a:0,b:2;path=a:1,b:3' },
  '18': { color: 'green', count: 1, code: 'path=a:0,b:3;path=a:1,b:2' },
  '19': { color: 'green', count: 2, code: 'path=a:0,b:3;path=a:2,b:4' },
  '20': { color: 'green', count: 2, code: 'path=a:0,b:3;path=a:1,b:4' },
  '23': { color: 'green', count: 3, code: 'path=a:0,b:3;path=a:0,b:4' },
  '24': { color: 'green', count: 3, code: 'path=a:0,b:3;path=a:0,b:2' },
  '25': { color: 'green', count: 3, code: 'path=a:0,b:2;path=a:0,b:4' },
  '26': { color: 'green', count: 2, code: 'path=a:0,b:3;path=a:0,b:5' },
  '27': { color: 'green', count: 2, code: 'path=a:0,b:3;path=a:0,b:1' },
  '28': { color: 'green', count: 2, code: 'path=a:0,b:4;path=a:0,b:5' },
  '29': { color: 'green', count: 2, code: 'path=a:0,b:2;path=a:0,b:1' },
  '87': { color: 'green', count: 2, code: 'town=revenue:10;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0' },
  '88': { color: 'green', count: 2, code: 'town=revenue:10;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0' },
  '203': { color: 'green', count: 2, code: 'town=revenue:10;path=a:0,b:_0;path=a:2,b:_0;path=a:4,b:_0' },
  '204': { color: 'green', count: 2, code: 'town=revenue:10;path=a:0,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0' },
  '205': { color: 'green', count: 1, code: 'city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0' },
  '206': { color: 'green', count: 1, code: 'city=revenue:30;path=a:0,b:_0;path=a:5,b:_0;path=a:3,b:_0' },
  '207': { color: 'green', count: 2, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;label=Y' },
  '208': { color: 'green', count: 2, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=Y' },
  '209': { color: 'green', count: 1, code: 'city=revenue:40,slots:3;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0;label=B' },
  '210': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:0,b:_0;path=a:3,b:_0;path=a:5,b:_1;path=a:4,b:_1;label=XX' },
  '211': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:1,b:_1;label=XX' },
  '212': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:5,b:_1;label=XX' },
  '213': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:4,b:_1;label=XX' },
  '214': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:4,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:2,b:_1;label=XX' },
  '215': { color: 'green', count: 1, code: 'city=revenue:30;city=revenue:30;path=a:1,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:4,b:_1;label=XX' },
  // Brown
  '39': { color: 'brown', count: 1, code: 'path=a:0,b:2;path=a:0,b:1;path=a:1,b:2' },
  '40': { color: 'brown', count: 1, code: 'path=a:0,b:2;path=a:2,b:4;path=a:0,b:4' },
  '41': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:0,b:1;path=a:1,b:3' },
  '42': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:3,b:5;path=a:0,b:5' },
  '43': { color: 'brown', count: 1, code: 'path=a:0,b:3;path=a:0,b:2;path=a:1,b:3;path=a:1,b:2' },
  '44': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:1,b:4;path=a:0,b:1;path=a:3,b:4' },
  '45': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:2,b:4;path=a:0,b:4;path=a:2,b:3' },
  '46': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:2,b:4;path=a:3,b:4;path=a:0,b:2' },
  '47': { color: 'brown', count: 2, code: 'path=a:0,b:3;path=a:1,b:4;path=a:1,b:3;path=a:0,b:4' },
  '63': { color: 'brown', count: 3, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0' },
  '70': { color: 'brown', count: 1, code: 'path=a:0,b:1;path=a:0,b:2;path=a:1,b:3;path=a:2,b:3' },
  '216': { color: 'brown', count: 4, code: 'city=revenue:50,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=Y' },
  '217': { color: 'brown', count: 2, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:4,b:_0;path=a:5,b:_0;path=a:3,b:_0;label=X' },
  '218': { color: 'brown', count: 2, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=X' },
  '219': { color: 'brown', count: 2, code: 'city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:5,b:_0;label=X' },
  '220': { color: 'brown', count: 1, code: 'city=revenue:60,slots:3;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0;label=B' },
  '221': { color: 'brown', count: 1, code: 'city=revenue:50,slots:3;path=a:_0,b:0;path=a:_0,b:1;path=a:_0,b:2;path=a:_0,b:3;path=a:_0,b:4;path=a:_0,b:5;label=HH' },
}

// --- parsed model ---------------------------------------------------------

export interface TileNodeDef {
  kind: NodeKind
  revenue: number
  slots: number
  edges: number[] // hex edges whose track meets this node
}

// A path endpoint is either a hex edge (0-5) or a node index.
export type PathEnd = { edge: number } | { node: number }

export interface TileDef {
  id: string
  color: TileColor
  count: number
  label?: string
  nodes: TileNodeDef[]
  paths: [PathEnd, PathEnd][]
}

function parseEnd(token: string): PathEnd {
  return token.startsWith('_') ? { node: Number(token.slice(1)) } : { edge: Number(token) }
}

function firstInt(s: string): number {
  const m = s.match(/\d+/)
  return m ? Number(m[0]) : 0
}

function parseTile(id: string, raw: RawTile): TileDef {
  const nodes: TileNodeDef[] = []
  const paths: [PathEnd, PathEnd][] = []
  let label: string | undefined

  for (const part of raw.code.split(';')) {
    const [head, rest = ''] = part.split('=')
    const attrs = Object.fromEntries(
      rest.split(',').map((kv) => {
        const [k, v = ''] = kv.split(':')
        return [k, v]
      }),
    )
    if (head === 'city' || head === 'town') {
      nodes.push({
        kind: head,
        revenue: firstInt(attrs.revenue ?? '0'),
        slots: attrs.slots ? Number(attrs.slots) : 1,
        edges: [],
      })
    } else if (head === 'path') {
      const a = parseEnd(attrs.a)
      const b = parseEnd(attrs.b)
      paths.push([a, b])
      // Record which edges feed each node, for node placement.
      for (const [end, other] of [
        [a, b],
        [b, a],
      ] as const) {
        if ('node' in end && 'edge' in other) nodes[end.node]?.edges.push(other.edge)
      }
    } else if (head === 'label') {
      label = rest
    }
  }
  return { id, color: raw.color, count: raw.count, label, nodes, paths }
}

export const TILE_DEFS: Record<string, TileDef> = Object.fromEntries(
  Object.entries(RAW_TILES).map(([id, raw]) => [id, parseTile(id, raw)]),
)

export function hasTileGeometry(tileId: string | number): boolean {
  return String(tileId) in TILE_DEFS
}

export function tilesByColor(color: TileColor): TileDef[] {
  return Object.values(TILE_DEFS)
    .filter((t) => t.color === color)
    .sort((a, b) => Number(a.id) - Number(b.id))
}

// --- geometry -------------------------------------------------------------

// Outward-normal direction (degrees, SVG: +x right, +y down) of each edge.
const EDGE_ANGLE_DEG: Record<number, number> = {
  0: -90, // N
  1: -30, // NE
  2: 30, // SE
  3: 90, // S
  4: 150, // SW
  5: 210, // NW
}

export interface Vec {
  x: number
  y: number
}

// Midpoint of a hex edge (on the apothem circle), relative to the hex centre.
export function edgePoint(edge: number, radius: number): Vec {
  const apothem = radius * Math.cos(Math.PI / 6) // ≈ 0.866 · R
  const a = (EDGE_ANGLE_DEG[edge] * Math.PI) / 180
  return { x: apothem * Math.cos(a), y: apothem * Math.sin(a) }
}

// Where to draw a node: pulled out from the centre toward the mean direction of
// its connected edges, so multiple stops on a tile don't overlap.
export function nodePosition(node: TileNodeDef, index: number, total: number, radius: number): Vec {
  if (total <= 1) return { x: 0, y: 0 }
  let sx = 0
  let sy = 0
  for (const e of node.edges) {
    const p = edgePoint(e, 1)
    sx += p.x
    sy += p.y
  }
  const mag = Math.hypot(sx, sy)
  const offset = radius * 0.42
  if (mag < 0.2) {
    // Edges cancel out (e.g. a straight): fan nodes around the centre instead.
    const a = (-90 + (index * 360) / total) * (Math.PI / 180)
    return { x: offset * Math.cos(a), y: offset * Math.sin(a) }
  }
  return { x: (sx / mag) * offset, y: (sy / mag) * offset }
}

function endPoint(end: PathEnd, nodePts: Vec[], radius: number): Vec {
  return 'edge' in end ? edgePoint(end.edge, radius) : nodePts[end.node]
}

// SVG path `d` for one track segment, relative to the hex centre (0,0).
export function segmentPath(seg: [PathEnd, PathEnd], nodePts: Vec[], radius: number): string {
  const pa = endPoint(seg[0], nodePts, radius)
  const pb = endPoint(seg[1], nodePts, radius)
  const bothEdges = 'edge' in seg[0] && 'edge' in seg[1]
  if (bothEdges) {
    const a = (seg[0] as { edge: number }).edge
    const b = (seg[1] as { edge: number }).edge
    const diff = Math.min((a - b + 6) % 6, (b - a + 6) % 6)
    if (diff === 3) return `M ${pa.x} ${pa.y} L ${pb.x} ${pb.y}` // straight
    return `M ${pa.x} ${pa.y} Q 0 0 ${pb.x} ${pb.y}` // curve via centre
  }
  // At least one endpoint is a node — draw straight stubs to it.
  return `M ${pa.x} ${pa.y} L ${pb.x} ${pb.y}`
}
