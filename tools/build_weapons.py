#!/usr/bin/env python3
"""Mirror the official CS2 weapon renders and build the weapon card data.

Images come from ByMykel/CSGO-API (MIT), which indexes Valve's own store
renders. We mirror them locally so the game works offline as a PWA and never
depends on Steam's CDN staying up.

Weapon FIT is a design rule, not a statistic: it reads a player's documented
role and asks whether that person would really be holding this gun. An AWP in
an AWPer's hands is the whole team's plan; an AWP handed to an entry fragger is
a broken team.
"""
import json
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
IMG = HERE.parent / "img" / "weapons"
OUT = HERE.parent / "data"
SRC = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/base_weapons.json"
UA = "13-0-drafting-game/0.1 (hobby project; malthewinther96@gmail.com)"

# The guns worth drafting, with the tier that decides how much a card is worth.
# tier: how much the weapon shapes a round.   fit: which roles it belongs to.
WEAPONS = {
    "AWP":            dict(slug="awp",      tier=3, fit={"awp": 6.0, "lurk": -1.0, "entry": -2.5, "support": -1.5, "igl": -1.0}),
    "SSG 08":         dict(slug="ssg08",    tier=2, fit={"awp": 3.5, "lurk": 1.0, "entry": 0.5, "support": 0.0, "igl": 0.0}),
    "AK-47":          dict(slug="ak47",     tier=3, fit={"entry": 4.0, "lurk": 3.5, "support": 2.5, "igl": 2.5, "awp": -1.0}),
    "M4A4":           dict(slug="m4a4",     tier=3, fit={"entry": 3.5, "lurk": 3.0, "support": 3.0, "igl": 2.5, "awp": -1.0}),
    "M4A1-S":         dict(slug="m4a1s",    tier=3, fit={"lurk": 4.0, "support": 3.0, "entry": 2.0, "igl": 2.5, "awp": -1.0}),
    "Galil AR":       dict(slug="galil",    tier=1, fit={"entry": 2.0, "support": 2.0, "lurk": 1.0, "igl": 1.5, "awp": -0.5}),
    "FAMAS":          dict(slug="famas",    tier=1, fit={"entry": 2.0, "support": 2.0, "lurk": 1.0, "igl": 1.5, "awp": -0.5}),
    "AUG":            dict(slug="aug",      tier=2, fit={"lurk": 2.5, "support": 2.0, "entry": 1.5, "igl": 1.5, "awp": 1.0}),
    "SG 553":         dict(slug="sg553",    tier=2, fit={"entry": 2.5, "lurk": 2.5, "support": 1.5, "igl": 1.5, "awp": 1.0}),
    "Desert Eagle":   dict(slug="deagle",   tier=2, fit={"lurk": 3.0, "entry": 2.5, "awp": 1.5, "support": 1.0, "igl": 1.5}),
    "USP-S":          dict(slug="usps",     tier=1, fit={"lurk": 1.5, "support": 1.5, "entry": 1.0, "igl": 1.0, "awp": 1.0}),
    "Glock-18":       dict(slug="glock",    tier=1, fit={"entry": 1.5, "support": 1.5, "lurk": 1.0, "igl": 1.0, "awp": 0.5}),
    "P250":           dict(slug="p250",     tier=1, fit={"support": 1.5, "lurk": 1.0, "entry": 1.0, "igl": 1.0, "awp": 1.0}),
    "Five-SeveN":     dict(slug="fiveseven", tier=1, fit={"support": 1.5, "lurk": 1.5, "entry": 1.0, "igl": 1.0, "awp": 0.5}),
    "Tec-9":          dict(slug="tec9",     tier=1, fit={"entry": 2.5, "support": 1.0, "lurk": 0.5, "igl": 0.5, "awp": 0.0}),
    "CZ75-Auto":      dict(slug="cz75",     tier=1, fit={"entry": 2.0, "support": 1.5, "lurk": 1.0, "igl": 1.0, "awp": 0.5}),
    "MP9":            dict(slug="mp9",      tier=1, fit={"support": 2.0, "entry": 1.5, "lurk": 0.5, "igl": 1.0, "awp": 0.0}),
    "MAC-10":         dict(slug="mac10",    tier=1, fit={"entry": 2.0, "support": 1.5, "lurk": 0.5, "igl": 1.0, "awp": 0.0}),
    "UMP-45":         dict(slug="ump45",    tier=1, fit={"support": 2.0, "entry": 1.5, "lurk": 1.0, "igl": 1.0, "awp": 0.0}),
    "P90":            dict(slug="p90",      tier=1, fit={"entry": 2.0, "support": 1.5, "lurk": 0.0, "igl": 0.5, "awp": -0.5}),
    "MP5-SD":         dict(slug="mp5sd",    tier=1, fit={"support": 2.0, "entry": 1.5, "lurk": 1.0, "igl": 1.0, "awp": 0.0}),
    "XM1014":         dict(slug="xm1014",   tier=1, fit={"support": 1.5, "entry": 1.0, "lurk": 0.5, "igl": 0.5, "awp": -0.5}),
    "Nova":           dict(slug="nova",     tier=1, fit={"support": 1.5, "entry": 1.0, "lurk": 0.5, "igl": 0.5, "awp": -0.5}),
    "MAG-7":          dict(slug="mag7",     tier=1, fit={"entry": 1.5, "support": 1.0, "lurk": 0.5, "igl": 0.5, "awp": -0.5}),
    "Negev":          dict(slug="negev",    tier=1, fit={"support": 1.0, "entry": 0.5, "lurk": 0.0, "igl": 0.0, "awp": -1.0}),
    "R8 Revolver":    dict(slug="r8",       tier=1, fit={"lurk": 1.5, "awp": 1.0, "entry": 0.5, "support": 0.5, "igl": 0.5}),
}


def fetch(url, headers=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA} if headers else {})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    index = json.loads(fetch(SRC))
    by_name = {w["name"]: w for w in index}

    cards = []
    for name, spec in WEAPONS.items():
        src = by_name.get(name)
        if not src:
            print(f"  !! {name} not in the API index")
            continue
        path = IMG / f"{spec['slug']}.png"
        if not path.exists():
            raw = fetch(src["image"], headers=False)
            path.write_bytes(raw)
            # 512x384 renders are far more than a phone card needs.
            im = Image.open(path).convert("RGBA")
            im.thumbnail((320, 240), Image.LANCZOS)
            im.save(path, optimize=True)
        cards.append({
            "n": name,
            "img": spec["slug"],
            "cat": src["category"]["name"],
            "tier": spec["tier"],
            "fit": spec["fit"],
        })
        print(f"  {name:15} {spec['slug']:10} {path.stat().st_size / 1024:6.1f} KB")

    OUT.mkdir(exist_ok=True)
    (OUT / "weapons.json").write_text(json.dumps(cards, separators=(",", ":"), ensure_ascii=False))
    total = sum((IMG / f"{c['img']}.png").stat().st_size for c in cards)
    print(f"\n{len(cards)} weapons -> data/weapons.json, art total {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
