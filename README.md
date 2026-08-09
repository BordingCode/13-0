# 13-0

A Counter-Strike drafting roguelite. Draft five players and five guns from real
rosters at real tournaments, then try to win a Major **without dropping a map**.

Inspired by [322-0](https://322-0.app) (the Dota 2 drafting game by Noxville).

Play: **https://bordingcode.github.io/13-0/**

## How a run works

1. **Packs.** Each pack is a real team at a real event — *fnatic · DreamHack Winter
   2014* — showing the five players who were actually on that roster that month,
   plus five guns. You take **one card per pack**.
2. **Roles.** Your team needs one AWPer, one in-game leader, one entry fragger, one
   lurker and one support. A player can only fill a slot their documented role covers.
3. **Chemistry.** Players who really played together bond; so do countrymen. Dragging a
   2014 legend into a 2021 lineup costs you.
4. **The Major.** Swiss Legends Stage — three wins to advance, three losses and you are
   out — then single-elimination best-of-three playoffs, MR12 scoring.

## Where the numbers come from

| Piece | Source |
| --- | --- |
| Player rating, K/D, rounds | HLTV career stats via [DSCKGEC/CS-GO-Professionals](https://github.com/DSCKGEC/CS-GO-Professionals) (MIT) |
| Roles, country, roster dates | [Liquipedia](https://liquipedia.net/counterstrike) (CC-BY-SA) |
| Team strength | Elo over 68,932 matches from [One-Studio/hltv-stats](https://github.com/One-Studio/hltv-stats) |
| Weapon renders | Valve art indexed by [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) (MIT) |

**Team ratings use the round as the unit, not the win** — in Counter-Strike the
scoreline is the dominance signal, so a 13-0 moves a rating much further than a 13-11,
and beating a strong team counts for more than beating a weak one. Series that recorded
only map counts are calibrated onto the same scale (a 2-0 reads as roughly a 13-5).

Player OVR blends four percentiles: RATING, DUELS, MILEAGE and **LEVEL** — how strong
the teams were that the player actually played for. Without LEVEL, the best card in the
game is a tier-2 grinder with a lot of rounds.

The tournament is the only invented part: your team never existed, so its run is
simulated. Real teams keep their real strength; no real result is ever reported.

### Known limits

- The player pool ends in 2022, so there is no donk or m0NESY — that is where the
  free data stops.
- Players whose Liquipedia role is now a non-playing job (coach, analyst) have no
  documented playing role, so f0rest, dupreeh, GuardiaN and ScreaM are not in the pool.
- Weapon fit is a **design rule** over documented roles, not a statistic. No kill
  counts are invented anywhere.

## Rebuilding the data

```bash
cd tools
python3 fetch_liquipedia.py   # roles + roster dates (respects the API rate limit)
python3 build_teams.py        # team Elo -> data/teams.json, data/events.json
python3 build_players.py      # player cards -> data/players.json
python3 build_packs.py        # packs + tournament fields
python3 build_weapons.py      # weapon art + data/weapons.json
```

`build_teams.py` needs `tools/matches_raw.json` (the match dump, gitignored — download
`matches.json` from One-Studio/hltv-stats).

## Development

Vanilla HTML/CSS/JS, no build step. Serve the folder and open it:

```bash
python3 -m http.server 8813
```

Debug hooks live on `window.__game` — `testRun(ovr, n)` plays *n* Majors with a team of
that rating and reports how often it wins and how often it goes flawless.

After editing `css/main.css` or `js/main.js`, bump the `?v=` in `index.html` **and** the
`CACHE` constant in `sw.js`, or browsers will serve the old file.
