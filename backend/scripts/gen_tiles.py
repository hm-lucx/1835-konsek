"""Generate the 1835 tile manifest (tiles.yml) from the authoritative catalogue.

Tile codes are taken verbatim from the 18xx engine (tobymao/18xx,
lib/engine/config/tile.rb) and the supply counts from its 1835 map
(lib/engine/game/g_1835/map.rb) — the same data 18xx.games uses. The frontend
renders the geometry; this script derives the logical manifest (colour, number
of cities, revenue, label, supply count) the backend needs.
"""
import io
import re
from pathlib import Path

# (color, count, verbatim 18xx tile code) keyed by tile id.
RAW_TILES = {
    # Yellow
    "1": ("yellow", 1, "town=revenue:10;town=revenue:10;path=a:1,b:_0;path=a:_0,b:3;path=a:0,b:_1;path=a:_1,b:4"),
    "2": ("yellow", 1, "town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:1,b:_1;path=a:_1,b:2"),
    "3": ("yellow", 2, "town=revenue:10;path=a:0,b:_0;path=a:_0,b:1"),
    "4": ("yellow", 3, "town=revenue:10;path=a:0,b:_0;path=a:_0,b:3"),
    "5": ("yellow", 3, "city=revenue:20;path=a:0,b:_0;path=a:1,b:_0"),
    "6": ("yellow", 3, "city=revenue:20;path=a:0,b:_0;path=a:2,b:_0"),
    "7": ("yellow", 8, "path=a:0,b:1"),
    "8": ("yellow", 16, "path=a:0,b:2"),
    "9": ("yellow", 12, "path=a:0,b:3"),
    "55": ("yellow", 1, "town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:1,b:_1;path=a:_1,b:4"),
    "56": ("yellow", 1, "town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:2;path=a:1,b:_1;path=a:_1,b:3"),
    "57": ("yellow", 2, "city=revenue:20;path=a:0,b:_0;path=a:_0,b:3"),
    "58": ("yellow", 4, "town=revenue:10;path=a:0,b:_0;path=a:_0,b:2"),
    "69": ("yellow", 2, "town=revenue:10;town=revenue:10;path=a:0,b:_0;path=a:_0,b:3;path=a:2,b:_1;path=a:_1,b:4"),
    "201": ("yellow", 2, "city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;label=Y"),
    "202": ("yellow", 2, "city=revenue:30;path=a:0,b:_0;path=a:2,b:_0;label=Y"),
    # Green
    "12": ("green", 2, "city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0"),
    "13": ("green", 2, "city=revenue:30;path=a:0,b:_0;path=a:2,b:_0;path=a:4,b:_0"),
    "14": ("green", 2, "city=revenue:30,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0"),
    "15": ("green", 2, "city=revenue:30,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0"),
    "16": ("green", 2, "path=a:0,b:2;path=a:1,b:3"),
    "18": ("green", 1, "path=a:0,b:3;path=a:1,b:2"),
    "19": ("green", 2, "path=a:0,b:3;path=a:2,b:4"),
    "20": ("green", 2, "path=a:0,b:3;path=a:1,b:4"),
    "23": ("green", 3, "path=a:0,b:3;path=a:0,b:4"),
    "24": ("green", 3, "path=a:0,b:3;path=a:0,b:2"),
    "25": ("green", 3, "path=a:0,b:2;path=a:0,b:4"),
    "26": ("green", 2, "path=a:0,b:3;path=a:0,b:5"),
    "27": ("green", 2, "path=a:0,b:3;path=a:0,b:1"),
    "28": ("green", 2, "path=a:0,b:4;path=a:0,b:5"),
    "29": ("green", 2, "path=a:0,b:2;path=a:0,b:1"),
    "87": ("green", 2, "town=revenue:10;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0"),
    "88": ("green", 2, "town=revenue:10;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0"),
    "203": ("green", 2, "town=revenue:10;path=a:0,b:_0;path=a:2,b:_0;path=a:4,b:_0"),
    "204": ("green", 2, "town=revenue:10;path=a:0,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0"),
    "205": ("green", 1, "city=revenue:30;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0"),
    "206": ("green", 1, "city=revenue:30;path=a:0,b:_0;path=a:5,b:_0;path=a:3,b:_0"),
    "207": ("green", 2, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;label=Y"),
    "208": ("green", 2, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=Y"),
    "209": ("green", 1, "city=revenue:40,slots:3;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0;label=B"),
    "210": ("green", 1, "city=revenue:30;city=revenue:30;path=a:0,b:_0;path=a:3,b:_0;path=a:5,b:_1;path=a:4,b:_1;label=XX"),
    "211": ("green", 1, "city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:1,b:_1;label=XX"),
    "212": ("green", 1, "city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:5,b:_1;label=XX"),
    "213": ("green", 1, "city=revenue:30;city=revenue:30;path=a:2,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:4,b:_1;label=XX"),
    "214": ("green", 1, "city=revenue:30;city=revenue:30;path=a:4,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:2,b:_1;label=XX"),
    "215": ("green", 1, "city=revenue:30;city=revenue:30;path=a:1,b:_0;path=a:3,b:_0;path=a:0,b:_1;path=a:4,b:_1;label=XX"),
    # Brown
    "39": ("brown", 1, "path=a:0,b:2;path=a:0,b:1;path=a:1,b:2"),
    "40": ("brown", 1, "path=a:0,b:2;path=a:2,b:4;path=a:0,b:4"),
    "41": ("brown", 2, "path=a:0,b:3;path=a:0,b:1;path=a:1,b:3"),
    "42": ("brown", 2, "path=a:0,b:3;path=a:3,b:5;path=a:0,b:5"),
    "43": ("brown", 1, "path=a:0,b:3;path=a:0,b:2;path=a:1,b:3;path=a:1,b:2"),
    "44": ("brown", 2, "path=a:0,b:3;path=a:1,b:4;path=a:0,b:1;path=a:3,b:4"),
    "45": ("brown", 2, "path=a:0,b:3;path=a:2,b:4;path=a:0,b:4;path=a:2,b:3"),
    "46": ("brown", 2, "path=a:0,b:3;path=a:2,b:4;path=a:3,b:4;path=a:0,b:2"),
    "47": ("brown", 2, "path=a:0,b:3;path=a:1,b:4;path=a:1,b:3;path=a:0,b:4"),
    "63": ("brown", 3, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0"),
    "70": ("brown", 1, "path=a:0,b:1;path=a:0,b:2;path=a:1,b:3;path=a:2,b:3"),
    "216": ("brown", 4, "city=revenue:50,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=Y"),
    "217": ("brown", 2, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:4,b:_0;path=a:5,b:_0;path=a:3,b:_0;label=X"),
    "218": ("brown", 2, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:4,b:_0;label=X"),
    "219": ("brown", 2, "city=revenue:40,slots:2;path=a:0,b:_0;path=a:1,b:_0;path=a:3,b:_0;path=a:5,b:_0;label=X"),
    "220": ("brown", 1, "city=revenue:60,slots:3;path=a:0,b:_0;path=a:1,b:_0;path=a:2,b:_0;path=a:3,b:_0;path=a:4,b:_0;path=a:5,b:_0;label=B"),
    "221": ("brown", 1, "city=revenue:50,slots:3;path=a:_0,b:0;path=a:_0,b:1;path=a:_0,b:2;path=a:_0,b:3;path=a:_0,b:4;path=a:_0,b:5;label=HH"),
}


def parse(code: str) -> tuple[int, int, str]:
    """Return (city_count, revenue, label) parsed from a tile code."""
    cities = len(re.findall(r"\bcity=", code))
    rev_match = re.search(r"revenue:(\d+)", code)
    revenue = int(rev_match.group(1)) if rev_match else 0
    label_match = re.search(r"label=([^;]+)", code)
    label = label_match.group(1) if label_match else ""
    return cities, revenue, label


def describe(color: str, cities: int, code: str) -> str:
    """Human-readable name for the manifest."""
    if cities >= 2:
        return f"{color.capitalize()} Doppelstadt"
    if cities == 1:
        return f"{color.capitalize()} Stadt"
    if "town=" in code:
        towns = len(re.findall(r"\btown=", code))
        return f"{color.capitalize()} Ort" + ("e" if towns >= 2 else "")
    return f"{color.capitalize()} Gleis"


out = io.StringIO()
out.write("# 1835 tile manifest — generated by scripts/gen_tiles.py.\n")
out.write("# Source: tobymao/18xx engine tile codes + 1835 supply counts.\n")
out.write("# Geometry lives in the frontend (tiles/tileGeometry.ts); this is the\n")
out.write("# logical manifest (colour / cities / revenue / label / supply count).\n")
out.write("tiles:\n")
for tid, (color, count, code) in sorted(RAW_TILES.items(), key=lambda kv: int(kv[0])):
    cities, revenue, label = parse(code)
    name = describe(color, cities, code)
    out.write(f"  - id: {tid}\n")
    out.write(f"    color: {color}\n")
    out.write(f'    name: "{name}"\n')
    out.write(f"    cities: {cities}\n")
    out.write(f"    value: {revenue}\n")
    out.write(f"    count: {count}\n")
    if label:
        out.write(f'    label: "{label}"\n')

path = Path(__file__).parent.parent / "src" / "eg1835" / "data" / "tiles.yml"
path.write_text(out.getvalue(), encoding="utf-8")
total = sum(c for _, c, _ in RAW_TILES.values())
print(f"wrote {len(RAW_TILES)} tile types ({total} total copies) to tiles.yml")
