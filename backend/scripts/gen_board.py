"""Generate the 1835 board (board.yml) faithfully from the printed map.

Coordinate model matches the renderer: flat-top hexes, q = column (left→right),
r = vertical band; odd q is offset half a hex downward. The printed letter rows
A–P collapse into r-bands of two letters each (A/B=0, C/D=1, … O/P=7).
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
    6: (2, 17),
    7: (3, 15),
}

# Water fringe along the northern coast (r0) and a couple of sea hexes.
WATER = [(q, 0) for q in range(7, 15)] + [(3, 1), (20, 1)]

# Mountains (70 M build cost) — the central/southern triangle hexes.
MOUNTAINS = [(9, 3), (11, 3), (8, 4), (10, 4), (12, 4), (14, 4),
             (8, 5), (15, 5), (8, 6), (6, 7), (12, 6)]

# Off-board red border regions (Fernverbindungen).
OFFBOARD = {
    (21, 0): "20/20/40",   # Ostpreußen
    (21, 4): "20/30/40",   # Oberschlesien
    (2, 6): "50",          # Elsaß-Lothringen
}

# Small nameless halts (black dots) scattered like the printed board.
TOWNS = [(9, 2), (14, 3), (5, 4), (16, 4), (10, 5), (4, 6), (13, 6), (7, 7)]

# Cities: (q, r) -> (name, value, marker, terrain)
# terrain "city" = white/printed station, "home" = grey company home,
# "citybrown" = pre-printed brown city (Braunschweig).
CITIES = {
    (11, 0): ("Kiel", "", "", "citywhite"),
    (10, 1): ("Hamburg", "50", "H", "city"),
    (12, 1): ("Schwerin", "", "M", "home"),
    (5, 1):  ("Oldenburg", "", "O", "home"),
    (7, 1):  ("Bremen", "50", "", "city"),
    (17, 2): ("Berlin", "50", "B", "city"),
    (8, 2):  ("Hannover", "", "", "citywhite"),
    (11, 2): ("Braunschweig", "", "", "citybrown"),
    (13, 2): ("Magdeburg", "", "3", "city"),
    (4, 3):  ("Essen/Duisburg", "50", "XX", "city"),
    (6, 3):  ("Dortmund", "", "4", "city"),
    (3, 3):  ("Düsseldorf", "", "Y", "city"),
    (16, 3): ("Leipzig", "", "S", "home"),
    (19, 3): ("Dresden", "", "Y", "citywhite"),
    (3, 4):  ("Köln", "50", "Y", "city"),
    (6, 4):  ("Mainz/Wiesbaden", "50", "XX", "city"),
    (8, 4):  ("Frankfurt", "50", "H", "city"),  # overrides mountain at (8,4)
    (5, 5):  ("Ludwigshafen/Mannheim", "", "B", "city"),
    (13, 5): ("Fürth/Nürnberg", "50", "XX", "city"),
    (7, 6):  ("Stuttgart", "", "W", "home"),
    (10, 6): ("Augsburg", "", "", "citywhite"),
    (3, 7):  ("Freiburg", "", "", "citywhite"),
    (14, 7): ("München", "", "Y", "home"),
}

# Build a terrain map; later entries win.
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
for (q, r), val in OFFBOARD.items():
    hexes[(q, r)] = dict(name="", terrain="offboard", value=val, marker="")
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

path = "/Users/victorritthaler/Documents/Hackathon/1835-konsek/backend/src/eg1835/data/board.yml"
open(path, "w").write(out.getvalue())
print(f"wrote {len(hexes)} hexes to board.yml")
