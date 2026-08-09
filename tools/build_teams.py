#!/usr/bin/env python3
"""Rate every team from 68,963 real matches (2012-2022) on one consistent scale.

The unit is the ROUND, not the win, because in Counter-Strike the scoreline is
the dominance signal — a 13-0 says something a 13-11 does not.

For each match, chronologically:
    expected round share  E = 1 / (1 + 10^((Rb - Ra)/400))
    actual round share    S = roundsA / (roundsA + roundsB)
    Ra += K * (S - E)

Series (bo3/bo5) only record map counts, not round scores, so their map share is
calibrated onto the round-share scale using the bo1 maps as the reference — see
`calibrate()`. That keeps both kinds of match speaking the same language.

Strength of schedule comes for free: beating a 1700 team moves you far more than
farming a 1200 team. Ratings regress toward the mean across long gaps, since a
team name outlives its roster.
"""
import json
import collections
import datetime
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "data"

START = 1500.0
K_MAP = 20.0
K_SERIES = 28.0        # a series carries more information than a single map
MAJOR_BOOST = 1.5
GAP_DAYS = 180         # after this long idle, regress toward the mean
GAP_REGRESSION = 0.25

SERIES = {"bo1", "bo2", "bo3", "bo5", "bo7"}


def load():
    matches = json.loads((HERE / "matches_raw.json").read_text())
    out = []
    for m in matches:
        try:
            a, b = int(m["team_a_score"]), int(m["team_b_score"])
            t = int(m["time"])
        except (ValueError, TypeError, KeyError):
            continue
        if a + b == 0:
            continue
        if not m.get("team_a_name") or not m.get("team_b_name"):
            continue
        out.append({
            "t": t,
            "a": m["team_a_name"].strip(),
            "b": m["team_b_name"].strip(),
            "sa": a, "sb": b,
            "kind": m.get("map_text", ""),
            "event": (m.get("event_name") or "").strip(),
            "event_id": m.get("event_id"),
        })
    out.sort(key=lambda x: x["t"])
    return out


def calibrate(matches):
    """Find the shrink factor that puts series map-share on the round-share scale.

    A 2-0 series gives a map share of 1.0, which would scream "total dominance"
    next to a 13-4 map (0.76). We shrink series shares toward 0.5 so that the
    average margin matches what single maps actually show.
    """
    map_margin = [abs(m["sa"] / (m["sa"] + m["sb"]) - 0.5)
                  for m in matches if m["kind"] not in SERIES]
    ser_margin = [abs(m["sa"] / (m["sa"] + m["sb"]) - 0.5)
                  for m in matches if m["kind"] in SERIES]
    mm = sum(map_margin) / len(map_margin)
    sm = sum(ser_margin) / len(ser_margin)
    return mm / sm, mm, sm, len(map_margin), len(ser_margin)


def main():
    matches = load()
    shrink, mm, sm, n_map, n_ser = calibrate(matches)
    print(f"{len(matches):,} matches  |  {n_map:,} single maps, {n_ser:,} series")
    print(f"mean margin: maps {mm:.3f}, series {sm:.3f} -> series shrink {shrink:.3f}")
    print(f"  a 2-0 series now reads as a {0.5 + shrink * 0.5:.2f} round share "
          f"(~13-{round(13 * (1 - (0.5 + shrink * 0.5)) / (0.5 + shrink * 0.5))})")

    elo = collections.defaultdict(lambda: START)
    last_seen = {}
    played = collections.Counter()
    # snapshots[event_id] = {team: rating at the end of that event}
    event_teams = collections.defaultdict(dict)
    event_meta = {}
    peak = {}

    for m in matches:
        a, b = m["a"], m["b"]
        day = m["t"] / 86400.0

        for team in (a, b):
            if team in last_seen and day - last_seen[team] > GAP_DAYS:
                elo[team] += (START - elo[team]) * GAP_REGRESSION
            last_seen[team] = day

        ra, rb = elo[a], elo[b]
        share = m["sa"] / (m["sa"] + m["sb"])
        if m["kind"] in SERIES:
            s = 0.5 + shrink * (share - 0.5)
            k = K_SERIES
        else:
            s = share
            k = K_MAP
        if "major" in m["event"].lower():
            k *= MAJOR_BOOST

        e = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
        delta = k * (s - e)
        elo[a] = ra + delta
        elo[b] = rb - delta
        played[a] += 1
        played[b] += 1

        eid = m["event_id"]
        if eid is not None:
            event_teams[eid][a] = elo[a]
            event_teams[eid][b] = elo[b]
            meta = event_meta.setdefault(eid, {"name": m["event"], "t": m["t"], "n": 0})
            meta["n"] += 1
            meta["t"] = max(meta["t"], m["t"])
        for team in (a, b):
            if played[team] >= 30 and elo[team] > peak.get(team, 0):
                peak[team] = elo[team]

    # --- convert Elo to a 0-100 OVR on one fixed scale ---
    pool = [v for t, v in elo.items() if played[t] >= 30]
    mean = sum(pool) / len(pool)
    var = sum((v - mean) ** 2 for v in pool) / len(pool)
    sd = var ** 0.5
    print(f"\n{len(pool):,} teams with 30+ matches | mean Elo {mean:.0f}, sd {sd:.0f}")

    def ovr(rating):
        return max(40, min(99, round(50 + 12 * (rating - mean) / sd)))

    # Keep events that were big enough to be a real tournament field.
    events = []
    for eid, teams in event_teams.items():
        meta = event_meta[eid]
        strong = {t: r for t, r in teams.items() if played[t] >= 30}
        if len(strong) < 8 or meta["n"] < 12:
            continue
        when = datetime.datetime.utcfromtimestamp(meta["t"])
        ranked = sorted(strong.items(), key=lambda kv: -kv[1])
        events.append({
            "id": eid,
            "name": meta["name"],
            "year": when.year,
            "ym": when.strftime("%Y-%m"),
            "teams": [{"n": t, "ovr": ovr(r)} for t, r in ranked],
        })
    events.sort(key=lambda e: (e["year"], e["name"]))

    teams_out = {t: {"ovr": ovr(r), "peak": ovr(peak.get(t, r)), "m": played[t]}
                 for t, r in elo.items() if played[t] >= 30}

    OUT.mkdir(exist_ok=True)
    (OUT / "teams.json").write_text(json.dumps(
        {"scale": {"mean": round(mean, 1), "sd": round(sd, 1)}, "teams": teams_out},
        separators=(",", ":"), ensure_ascii=False))
    (OUT / "events.json").write_text(json.dumps(events, separators=(",", ":"), ensure_ascii=False))
    print(f"{len(events):,} usable events -> data/events.json")

    best = sorted(teams_out.items(), key=lambda kv: -kv[1]["peak"])[:15]
    print("\nhighest peak team ratings:")
    for name, d in best:
        print(f"  {d['peak']:3d} peak  {d['ovr']:3d} final  {name:22} {d['m']:,} matches")


if __name__ == "__main__":
    main()
