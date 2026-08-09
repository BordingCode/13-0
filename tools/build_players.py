#!/usr/bin/env python3
"""Turn the raw career CSV + Liquipedia data into the game's player cards.

Every number on a card traces back to real data:
  RATING  = HLTV career rating          DUELS = K/D ratio
  MILEAGE = rounds played (longevity)   role  = Liquipedia's documented role

OVR is a percentile blend rather than a raw rescale, because HLTV ratings bunch
tightly (0.90-1.27) and a linear map would make every card look identical. The
blend is 72% pool-wide and 28% within-role, so in-game leaders — who post lower
ratings by the nature of the job — are judged partly against their own kind
without flattening the scale.

A career rating says nothing about who you played against: a 1.17 farmed in a
tier-2 league is not a 1.17 against Astralis. So LEVEL — how strong the teams a
player actually played for were, taken from the team Elo in build_teams.py —
is folded in as its own component. Without it the pool's top card is a tier-2
grinder with a lot of rounds, which is both wrong and boring.
"""
import ast
import csv
import json
from bisect import bisect_left
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "data"

# Liquipedia's role vocabulary is inconsistent; fold it down to five team slots.
ROLE_ALIASES = {
    "awp": "awp", "awper": "awp",
    "igl": "igl",
    "entry": "entry", "entryfragger": "entry",
    "lurk": "lurk", "lurker": "lurk",
    "support": "support",
    "rifle": "rifle", "rifler": "rifle",
}
SLOTS = ["awp", "igl", "entry", "lurk", "support"]
# A generic rifler can credibly fill any of the three non-specialist slots.
SLOTS_FOR = {
    "awp": ["awp"], "igl": ["igl"], "entry": ["entry"],
    "lurk": ["lurk"], "support": ["support"],
    "rifle": ["entry", "lurk", "support"],
}

FLAGS = {
    "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Ukraine": "🇺🇦", "Russia": "🇷🇺", "France": "🇫🇷",
    "Brazil": "🇧🇷", "United States": "🇺🇸", "Canada": "🇨🇦", "Poland": "🇵🇱", "Norway": "🇳🇴",
    "Finland": "🇫🇮", "Germany": "🇩🇪", "Bosnia and Herzegovina": "🇧🇦", "Slovakia": "🇸🇰",
    "Czech Republic": "🇨🇿", "Estonia": "🇪🇪", "Latvia": "🇱🇻", "Lithuania": "🇱🇹",
    "Israel": "🇮🇱", "Turkey": "🇹🇷", "Spain": "🇪🇸", "Portugal": "🇵🇹", "United Kingdom": "🇬🇧",
    "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Australia": "🇦🇺", "Kazakhstan": "🇰🇿",
    "Bulgaria": "🇧🇬", "Romania": "🇷🇴", "Serbia": "🇷🇸", "Slovenia": "🇸🇮", "Croatia": "🇭🇷",
    "Hungary": "🇭🇺", "Austria": "🇦🇹", "Switzerland": "🇨🇭", "Belarus": "🇧🇾", "China": "🇨🇳",
    "Mongolia": "🇲🇳", "Argentina": "🇦🇷", "Chile": "🇨🇱", "Uruguay": "🇺🇾", "Moldova": "🇲🇩",
    "New Zealand": "🇳🇿", "South Africa": "🇿🇦", "Indonesia": "🇮🇩", "Malaysia": "🇲🇾",
    "Singapore": "🇸🇬", "Thailand": "🇹🇭", "Philippines": "🇵🇭", "India": "🇮🇳", "Japan": "🇯🇵",
    "South Korea": "🇰🇷", "Italy": "🇮🇹", "Greece": "🇬🇷", "Ireland": "🇮🇪", "Iceland": "🇮🇸",
}


def pct_ranker(values):
    """Return f(v) -> percentile 0..1 of v within values."""
    ordered = sorted(values)
    n = len(ordered)
    return lambda v: bisect_left(ordered, v) / max(1, n - 1)


def main():
    lq = json.loads((HERE / "liquipedia.json").read_text())
    team_ovr = {n: t["peak"] for n, t in json.loads((OUT / "teams.json").read_text())["teams"].items()}

    raw = []
    for row in csv.DictReader(open(HERE / "cs_players_raw.csv", encoding="utf-8")):
        name = row["Name"].strip()
        info = lq.get(name)
        if not info:
            continue
        roles = []
        for r in info["roles"]:
            slot = ROLE_ALIASES.get(r)
            if slot and slot not in roles:
                roles.append(slot)
        if not roles:
            continue  # no documented playing role -> not a draftable card
        try:
            rating = float(row["HLTV Rating"])
            kd = float(row["K/D Ratio"])
            rounds = int(row["Number of Rounds Played"])
            maps = int(row["Number of Maps Played"])
        except (ValueError, KeyError):
            continue
        if rounds < 2000:
            continue  # too small a sample for the numbers to mean anything

        try:
            teams = [t.strip() for t in ast.literal_eval("[" + row["Teams Played In"] + "]")]
        except (ValueError, SyntaxError):
            teams = []

        # How strong were the teams this player actually played for? Their best
        # team counts most — that is the level they proved themselves at — with
        # the rest of the career keeping a one-off stint honest.
        levels = [team_ovr[t] for t in teams if t in team_ovr]
        level = (0.65 * max(levels) + 0.35 * (sum(levels) / len(levels))) if levels else 55.0

        raw.append({
            "name": name,
            "roles": roles,
            "level": level,
            "bestTeam": max(teams, key=lambda t: team_ovr.get(t, 0)) if levels else (teams[0] if teams else ""),
            "country": info["country"],
            "flag": FLAGS.get(info["country"], "🏳"),
            "rating": rating,
            "kd": kd,
            "rounds": rounds,
            "maps": maps,
            "csvTeams": teams,
            "stints": info["teams"],
        })

    # --- scale the three shown stats to 0-99 by percentile ---
    r_rank = pct_ranker([p["rating"] for p in raw])
    d_rank = pct_ranker([p["kd"] for p in raw])
    m_rank = pct_ranker([p["rounds"] for p in raw])
    l_rank = pct_ranker([p["level"] for p in raw])
    for p in raw:
        p["_r"], p["_d"] = r_rank(p["rating"]), d_rank(p["kd"])
        p["_m"], p["_l"] = m_rank(p["rounds"]), l_rank(p["level"])
        p["core"] = 0.47 * p["_r"] + 0.18 * p["_d"] + 0.11 * p["_m"] + 0.24 * p["_l"]

    by_role = {}
    for p in raw:
        by_role.setdefault(p["roles"][0], []).append(p["core"])
    role_rank = {r: pct_ranker(v) for r, v in by_role.items()}

    players = []
    for p in raw:
        blended = 0.72 * p["core"] + 0.28 * role_rank[p["roles"][0]](p["core"])
        slots = []
        for r in p["roles"]:
            for s in SLOTS_FOR[r]:
                if s not in slots:
                    slots.append(s)
        players.append({
            "n": p["name"],
            "f": p["flag"],
            "c": p["country"],
            "r": p["roles"],            # documented roles, in Liquipedia's order
            "s": slots,                 # team slots this player can fill
            "ovr": round(40 + 59 * blended),
            "rat": round(99 * p["_r"]),   # RATING  (HLTV career rating)
            "duel": round(99 * p["_d"]),  # DUELS   (K/D ratio)
            "mil": round(99 * p["_m"]),   # MILEAGE (rounds played)
            "lvl": round(99 * p["_l"]),   # LEVEL   (strength of teams played for)
            "best": p["bestTeam"],
            "hltv": p["rating"],
            "kd": p["kd"],
            "maps": p["maps"],
            "rounds": p["rounds"],
            "teams": p["csvTeams"],
            "stints": p["stints"],
        })

    players.sort(key=lambda p: -p["ovr"])
    OUT.mkdir(exist_ok=True)
    (OUT / "players.json").write_text(json.dumps(players, separators=(",", ":"), ensure_ascii=False))

    print(f"{len(players)} player cards -> data/players.json")
    counts = {s: sum(1 for p in players if s in p["s"]) for s in SLOTS}
    print("eligible per slot:", counts)
    print("\ntop 15:")
    for p in players[:15]:
        print(f"  {p['ovr']:3d} {p['f']} {p['n']:14} {'/'.join(p['r']):14} {p['best']:14}"
              f"rating {p['hltv']:.2f}  K/D {p['kd']:.2f}  {p['rounds']:,} rounds")


if __name__ == "__main__":
    main()
