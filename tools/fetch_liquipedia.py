#!/usr/bin/env python3
"""Fetch role / country / team-history for every player in the career CSV.

Liquipedia's API terms: gzip required, descriptive User-Agent, and no more than
one non-parse request every 2 seconds. We batch 50 page titles per request and
sleep 2.5s between them, so the whole roster costs well under a minute.

Raw wikitext is cached to disk so re-runs are free.
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "cache_liquipedia.json"
API = "https://liquipedia.net/counterstrike/api.php"
UA = "13-0-drafting-game/0.1 (hobby project; malthewinther96@gmail.com)"
BATCH = 50
SLEEP = 2.5


def api_get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip

        raw = gzip.decompress(raw)
    return json.loads(raw)


def fetch_batch(titles):
    """Return {requested_title: wikitext} for a batch of page titles."""
    data = api_get(
        {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "redirects": 1,
            "format": "json",
            "titles": "|".join(titles),
        }
    )
    q = data.get("query", {})
    # Map whatever the API normalised/redirected our titles into, back to what we asked for.
    alias = {}
    for kind in ("normalized", "redirects"):
        for entry in q.get(kind, []) or []:
            alias[entry["to"]] = alias.get(entry["from"], entry["from"])

    out = {}
    for page in q.get("pages", {}).values():
        title = page.get("title", "")
        asked = alias.get(title, title)
        if "revisions" not in page:
            continue
        out[asked] = page["revisions"][0]["slots"]["main"]["*"]
    return out


def field(text, name):
    m = re.search(r"^\|%s\s*=\s*(.*?)\s*$" % re.escape(name), text, re.M)
    return m.group(1) if m else ""


def team_history(text):
    """Parse {{TH|2016-08-04 — 2023-10-26|Natus Vincere}} rows into stints."""
    stints = []
    for m in re.finditer(r"\{\{TH\|([^|}]*)\|([^|}]*)((?:\|[^}]*)?)\}\}", text):
        span, team, rest = m.group(1), m.group(2).strip(), m.group(3)
        if not team:
            continue
        # Skip stand-in / loan / inactive stints: they aren't "really" that roster.
        if re.search(r"\|(Stand-in|Loan|Inactive)", rest, re.I):
            continue
        dates = re.findall(r"(\d{4})-(\d{2}|\?\?)-(?:\d{2}|\?\?)", span)
        if not dates:
            continue
        start = f"{dates[0][0]}-{dates[0][1] if dates[0][1] != '??' else '01'}"
        if len(dates) > 1:
            end = f"{dates[1][0]}-{dates[1][1] if dates[1][1] != '??' else '12'}"
        else:
            end = "2022-12" if "Present" in span else start
        stints.append({"team": team, "from": start, "to": end})
    return stints


def main():
    names = []
    with open(HERE / "cs_players_raw.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Name"].strip():
                names.append(row["Name"].strip())

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [n for n in names if n not in cache]
    print(f"{len(names)} players, {len(todo)} to fetch", flush=True)

    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        try:
            got = fetch_batch(batch)
        except Exception as e:  # keep whatever we already have on a network hiccup
            print(f"  batch {i}: {e}", file=sys.stderr, flush=True)
            time.sleep(10)
            continue
        for n in batch:
            cache[n] = got.get(n, None)  # None = no Liquipedia page found
        hit = sum(1 for n in batch if cache.get(n))
        print(f"  {i + len(batch):4d}/{len(todo)}  +{hit}/{len(batch)} found", flush=True)
        CACHE.write_text(json.dumps(cache))
        time.sleep(SLEEP)

    players = {}
    for name, text in cache.items():
        if not text:
            continue
        players[name] = {
            "roles": [r.strip().lower() for r in field(text, "roles").split(",") if r.strip()],
            "country": field(text, "country"),
            "birth": field(text, "birth_date"),
            "teams": team_history(text),
        }
    (HERE / "liquipedia.json").write_text(json.dumps(players, indent=0))
    found = len(players)
    with_roles = sum(1 for p in players.values() if p["roles"])
    with_teams = sum(1 for p in players.values() if p["teams"])
    print(f"\nwrote liquipedia.json: {found}/{len(names)} pages, "
          f"{with_roles} with roles, {with_teams} with team history")


if __name__ == "__main__":
    main()
