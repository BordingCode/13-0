#!/usr/bin/env python3
"""Build the draft packs: a real team, at a real tournament, with its real five.

This is the join that makes the game feel like history rather than a card
shuffle. Liquipedia team histories carry exact date ranges, so for any event we
can ask who was actually on that roster that month — and only keep the pairings
where five of them are in the player pool.

Also emits the tournament fields the run is played against: the same events,
with their real teams at the rating they had earned by then.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data"

MIN_ROSTER = 5
# A pack should be a team people have heard of, at an event that mattered.
MIN_TEAM_OVR = 56
FIELD_SIZE = 16

# The tournaments you actually play. Named one by one rather than guessed at,
# because "major" in an event name also matches "PGL Major Krakow 2017 Main
# Qualifier" — and a qualifier is not the thing the game is named after. Every
# one of these is a real CS:GO Major with a real 16-team field; ESL One Cologne
# 2014 and IEM Rio 2022 are the two missing, the first short a team in the match
# feed and the second past where the data ends.
MAJORS = {
    "DreamHack Winter 2013",
    "EMS One Katowice 2014",
    "DreamHack Winter 2014",
    "ESL One Katowice 2015",
    "ESL One Cologne 2015",
    "DreamHack Open Cluj-Napoca 2015",
    "MLG Columbus 2016",
    "ESL One Cologne 2016",
    "ELEAGUE Major 2017",
    "PGL Major Krakow 2017",
    "ELEAGUE Major 2018",
    "FACEIT Major 2018",
    "IEM Katowice 2019",
    "StarLadder Major Berlin 2019",
    "IEM Katowice 2020",
    "PGL Major Stockholm 2021",
    "PGL Major Antwerp 2022",
}

# Team names differ between HLTV's match feed and Liquipedia's team histories.
ALIASES = {
    "Natus Vincere": {"Natus Vincere", "Na'Vi", "NaVi"},
    "Ninjas in Pyjamas": {"Ninjas in Pyjamas", "NiP"},
    "Virtus.pro": {"Virtus.pro", "Virtus Pro", "VP"},
    "MOUZ": {"MOUZ", "mousesports", "Mousesports"},
    "FaZe": {"FaZe", "FaZe Clan"},
    "G2": {"G2", "G2 Esports"},
    "Liquid": {"Liquid", "Team Liquid"},
    "Vitality": {"Vitality", "Team Vitality"},
    "NRG": {"NRG", "NRG Esports"},
    "Cloud9": {"Cloud9", "C9"},
    "Heroic": {"Heroic", "Team Heroic"},
    "Gambit": {"Gambit", "Gambit Esports", "Gambit Youngsters", "Gambit Gaming"},
    "Astralis": {"Astralis"},
    "fnatic": {"fnatic", "Fnatic"},
    "SK": {"SK", "SK Gaming"},
    "Luminosity": {"Luminosity", "Luminosity Gaming"},
    "ENCE": {"ENCE", "ENCE eSports"},
    "OG": {"OG", "OG Esports"},
    "BIG": {"BIG", "BIG Clan"},
    "Spirit": {"Spirit", "Team Spirit"},
    "forZe": {"forZe", "forZe eSports"},
    "Dignitas": {"Dignitas", "Team Dignitas"},
    "EG": {"EG", "Evil Geniuses"},
    "compLexity": {"compLexity", "compLexity Gaming", "Complexity"},
    "TSM": {"TSM", "Team SoloMid"},
    "Envy": {"Envy", "Team EnVyUs", "EnVyUs"},
    "Renegades": {"Renegades"},
    "TYLOO": {"TYLOO", "Tyloo"},
    "MIBR": {"MIBR"},
    "furia": {"furia", "FURIA", "FURIA Esports"},
    "GODSENT": {"GODSENT", "Godsent"},
    "North": {"North"},
    "Sprout": {"Sprout"},
    "Entropiq": {"Entropiq"},
    "Movistar Riders": {"Movistar Riders"},
    "Eternal Fire": {"Eternal Fire"},
    "Space Soldiers": {"Space Soldiers"},
    "AGO": {"AGO", "AGO Esports"},
    "Endpoint": {"Endpoint", "Team Endpoint"},
    "Copenhagen Flames": {"Copenhagen Flames"},
    "SAW": {"SAW"},
    "Nemiga": {"Nemiga", "Nemiga Gaming"},
}


def norm(name):
    """Loose key so 'Team Liquid' and 'Liquid' land in the same bucket."""
    n = name.lower().strip()
    n = re.sub(r"\b(team|gaming|esports|e-sports|clan|academy)\b", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def main():
    players = json.loads((DATA / "players.json").read_text())
    events = json.loads((DATA / "events.json").read_text())
    teams = json.loads((DATA / "teams.json").read_text())["teams"]

    # name-key -> canonical HLTV name
    canon = {}
    for main_name, variants in ALIASES.items():
        for v in variants:
            canon[norm(v)] = main_name
    for t in teams:
        canon.setdefault(norm(t), t)

    # canonical team -> [(from, to, player)] from Liquipedia's dated stints
    roster = defaultdict(list)
    by_name = {}
    for p in players:
        by_name[p["n"]] = p
        for st in p["stints"]:
            key = canon.get(norm(st["team"]))
            if key:
                roster[key].append((st["from"], st["to"], p["n"]))

    packs = []
    fields = []
    for ev in events:
        ym = ev["ym"]
        # The field is the event's real attendance, weak teams included. An
        # earlier cut at ovr>=55 quietly deleted the bottom of a Major — Bravado
        # and myXMG were at DreamHack Winter 2014 — which left the Legends Stage
        # with an odd number of teams and no way to resolve it.
        if ev["name"] in MAJORS and len(ev["teams"]) >= FIELD_SIZE:
            fields.append({
                "name": ev["name"],
                "year": ev["year"],
                "teams": ev["teams"][:FIELD_SIZE],
            })

        for t in ev["teams"]:
            if t["ovr"] < MIN_TEAM_OVR:
                continue
            here = [n for (a, b, n) in roster.get(t["n"], []) if a <= ym <= b]
            # Dedupe, then take the strongest five — big orgs list subs too.
            here = sorted(set(here), key=lambda n: -by_name[n]["ovr"])[:MIN_ROSTER]
            if len(here) < MIN_ROSTER:
                continue
            packs.append({
                "team": t["n"],
                "event": ev["name"],
                "year": ev["year"],
                "ovr": t["ovr"],
                "players": here,
            })

    # One pack per team+year keeps the draft from showing the same five twice.
    seen = {}
    for p in packs:
        key = (p["team"], p["year"])
        if key not in seen or p["ovr"] > seen[key]["ovr"]:
            seen[key] = p
    packs = sorted(seen.values(), key=lambda p: (p["year"], p["team"]))

    # One entry per Major, strongest attendance kept if a name somehow repeats.
    seen_field = {}
    for f in fields:
        if f["name"] not in seen_field:
            seen_field[f["name"]] = f
    fields = sorted(seen_field.values(), key=lambda f: (f["year"], f["name"]))

    (DATA / "packs.json").write_text(json.dumps(packs, separators=(",", ":"), ensure_ascii=False))
    (DATA / "fields.json").write_text(json.dumps(fields, separators=(",", ":"), ensure_ascii=False))

    used = {n for p in packs for n in p["players"]}
    print(f"{len(packs)} packs across {len({p['team'] for p in packs})} teams, "
          f"{len(used)} distinct players drafted")
    print(f"{len(fields)} tournament fields ({fields[0]['year']}-{fields[-1]['year']})")
    print("\nsample packs:")
    for p in packs[:6] + packs[-6:]:
        print(f"  {p['year']}  {p['ovr']:3d}  {p['team']:18} {p['event'][:34]:36} "
              f"{', '.join(p['players'])}")
    print("\nsample field:")
    f = fields[len(fields) // 2]
    print(f"  {f['name']} ({f['year']}): " + ", ".join(f"{t['n']} {t['ovr']}" for t in f["teams"][:8]))


if __name__ == "__main__":
    main()
