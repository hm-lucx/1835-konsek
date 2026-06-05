"""Generate the 1835 board (board.yml) faithfully from the printed map.

Coordinate model matches the renderer: flat-top hexes, q = column (left→right),
r = vertical band; odd q is offset half a hex downward. The printed letter rows
A–P collapse into r-bands of two letters each (A/B=0, C/D=1, … O/P=7).

Mapping from map_data.json coordinates (e.g. "C11"):
  row letter → r-band: A/B=0, C/D=1, E/F=2, G/H=3, I/J=4, K/L=5, M/N=6, O/P=7
  column number → q:  q = col - 1
"""
import io

W, H = 22, 8

# --- plain land fill per r-band: inclusive q range ------------------------
LAND = {
    1: (4, 20),
    2: (3, 20),
    3: (2, 21),
    4: (2, 21),
    5: (2, 18),
    6: (1, 17),
    7: (3, 15),
}

# Northern sea — r=0 band is mostly water.
# Kiel (B7 → q=6) splits the sea: North Sea west, Baltic east.
WATER = (
    [(q, 0) for q in [4, 5]]           # North Sea west of Kiel
    + [(q, 0) for q in range(7, 21)]   # Baltic Sea east of Kiel (q=7..20)
    + [(3, 1)]                         # Frisian coast inlet (west)
)

# Mountains (70 M build cost) — from map_data.json terrain_hexes, q=col-1, r=band.
# H7=(6,3) conflicts with Dortmund city → city wins, mountain skipped.
# I8=(7,4) conflicts with Mainz/Wiesbaden city → city wins.
MOUNTAINS = [
    (8, 3), (10, 3), (11, 3),          # H9 Westerwald, G11 Harz, H12 Thüringer Wald
    (7, 4), (9, 4), (12, 4), (15, 4),  # I8 Taunus(overridden), I10 Rhön, I13 Erzgebirge, J16 Böhmerwald
    (14, 5),                            # K15 Bayer. Voralpen
    (7, 6),                             # N8 Schwarzwald
    (6, 7),                             # O7 Süd-Schwarzwald / Vogesen
]

# Off-board red border regions.
# Coordinates from map_data.json, mapped via q=col-1, r=band.
OFFBOARD = {
    (20, 1): ("20/30/40", "Ostpreußen"),      # C21 → q=20, r=1
    (20, 4): ("20/30/40", "Oberschlesien"),   # I21 → q=20, r=4
    (1, 6):  ("50/60",    "Elsaß-Lothringen"), # M2 → q=1, r=6
}

# Small nameless halts (black dots).
TOWNS = [(5, 4), (16, 4), (10, 5), (4, 6), (13, 6), (7, 7)]

# Cities: (q, r) → (name, value, marker, terrain)
# Coordinates from map_data.json, mapped via q=col-1, r=band.
CITIES = {
    (6,  0): ("Kiel",                  "",    "",   "citywhite"),  # B7
    (10, 1): ("Hamburg",               "50",  "H",  "city"),       # C11
    (11, 1): ("Schwerin",              "",    "M",  "home"),       # C12
    (8,  1): ("Oldenburg",             "",    "O",  "home"),       # D9
    (9,  1): ("Bremen",                "50",  "",   "city"),       # D10
    (17, 2): ("Berlin",                "50",  "B",  "city"),       # E18
    (7,  2): ("Hannover",              "",    "",   "citywhite"),  # F8
    (9,  2): ("Braunschweig",          "",    "",   "citybrown"),  # F10
    (12, 2): ("Magdeburg",             "",    "3",  "city"),       # F13
    (4,  3): ("Essen/Duisburg",        "50",  "XX", "city"),       # G5
    (6,  3): ("Dortmund",              "",    "4",  "city"),       # G7
    (3,  3): ("Düsseldorf",            "",    "Y",  "city"),       # H4
    (14, 3): ("Leipzig",               "",    "S",  "home"),       # H15
    (19, 3): ("Dresden",               "",    "Y",  "citywhite"),  # H20
    (4,  4): ("Köln",                  "50",  "Y",  "city"),       # I5
    (7,  4): ("Mainz/Wiesbaden",       "50",  "XX", "city"),       # J8
    (8,  4): ("Frankfurt",             "50",  "H",  "city"),       # J9
    (6,  5): ("Ludwigshafen/Mannheim", "",    "B",  "city"),       # L7
    (13, 5): ("Fürth/Nürnberg",        "50",  "XX", "city"),       # L14
    (8,  6): ("Stuttgart",             "",    "W",  "home"),       # M9
    (11, 6): ("Augsburg",              "",    "",   "citywhite"),  # N12
    (13, 7): ("München",               "",    "Y",  "home"),       # O14
    (4,  7): ("Freiburg",              "",    "",   "citywhite"),  # O5
}

# Build a terrain map; later entries win (cities override mountains/towns).
hexes = {}  # (q, r) -> dict
for r, (lo, hi) in LAND.items():
    for q in range(lo, hi + 1):
        hexes[(q, r)] = dict(name="", terrain="plain", value="", marker="")
for q, r in WATER:
    hexes[(q, r)] = dict(name="", terrain="water", value="", marker="")
for q, r in TOWNS:
    hexes[(q, r)] = dict(name="", terrain="town", value="", marker="")
for q, r in MOUNTAINS:
    hexes[(q, r)] = dict(name="", terrain="mountain", value="70", marker="")
for (q, r), (val, name) in OFFBOARD.items():
    hexes[(q, r)] = dict(name=name, terrain="offboard", value=val, marker="")
for (q, r), (name, val, mk, terr) in CITIES.items():
    hexes[(q, r)] = dict(name=name, terrain=terr, value=val, marker=mk)

# Emit YAML (sorted for stable output).
out = io.StringIO()
out.write("# 1835 Konsek Board Layout — reconstructed from the printed map.\n")
out.write("# Flat-top hexes: q = column (left→right), r = band (odd q offset down).\n")
out.write("# terrain: plain | town | city | home | citybrown | mountain | water | offboard\n")
out.write("board:\n")
out.write(f"  width: {W}\n  height: {H}\n  positions:\n")
for (q, r) in sorted(hexes, key=lambda k: (k[1], k[0])):
    h = hexes[(q, r)]
    out.write(f"    - q: {q}\n      r: {r}\n      tile_id: 0\n")
    out.write(f"      terrain: \"{h['terrain']}\"\n")
    if h["name"]:
        out.write(f"      name: \"{h['name']}\"\n")
    if h["value"]:
        out.write(f"      value: \"{h['value']}\"\n")
    if h["marker"]:
        out.write(f"      marker: \"{h['marker']}\"\n")

from pathlib import Path
path = Path(__file__).parent.parent / "src" / "eg1835" / "data" / "board.yml"
path.write_text(out.getvalue(), encoding="utf-8")
print(f"wrote {len(hexes)} hexes to board.yml")
