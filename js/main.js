/* 13-0 — a Counter-Strike drafting roguelite.
   Vanilla, no build step. Data lives in data/*.json, built by tools/*.py. */
(function () {
  'use strict';

  // ---------------------------------------------------------------- data
  var DATA = {};
  var byName = {};

  var SLOTS = ['awp', 'igl', 'entry', 'lurk', 'support'];
  var SLOT_LABEL = { awp: 'AWP', igl: 'IGL', entry: 'Entry', lurk: 'Lurk', support: 'Support' };

  var ERAS = [
    { id: 'all', label: 'All-time', desc: 'Every roster from 2013 to 2022.', from: 2000, to: 3000 },
    { id: 'golden', label: 'Golden era', desc: 'fnatic, NiP, Astralis rising — 2013 to 2017.', from: 2013, to: 2017 },
    { id: 'modern', label: 'Modern', desc: 'Astralis, NaVi, Vitality — 2018 to 2022.', from: 2018, to: 2022 }
  ];
  var DIFFS = [
    { id: 'hard', label: 'Hard', desc: 'No rerolls. What you are shown is what you get.', rerolls: 0 },
    { id: 'pro', label: 'Pro', desc: 'One reroll for a pack you cannot use.', rerolls: 1 },
    { id: 'smurf', label: 'Smurfing', desc: 'Two rerolls.', rerolls: 2 }
  ];
  var ALLOCS = [
    { id: 'auto', label: 'Automatic', desc: 'Each gun goes to whoever fits it best.' },
    { id: 'manual', label: 'Manual', desc: 'You choose who carries what, in draft order.' }
  ];

  var setup = { era: 'all', diff: 'pro', alloc: 'auto' };
  var run = null;

  // ---------------------------------------------------------------- helpers
  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function screen(name) {
    var all = document.querySelectorAll('.screen');
    for (var i = 0; i < all.length; i++) all[i].classList.remove('active');
    var s = $('screen-' + name);
    if (s) s.classList.add('active');
    window.scrollTo(0, 0);
  }

  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  function shuffled(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

  // ---------------------------------------------------------------- rating model
  //
  // Team OVR = the five players' average, plus how well the guns suit them,
  // plus chemistry. Chemistry is real history: who actually played together,
  // who shares a language, and whether these five belong to the same era.

  function bondPairs(squad) {
    // Two players bond if their Liquipedia stints overlap on the same team.
    var n = 0, shared = [];
    for (var i = 0; i < squad.length; i++) {
      for (var j = i + 1; j < squad.length; j++) {
        var a = squad[i].p.stints, b = squad[j].p.stints;
        var hit = null;
        for (var x = 0; x < a.length && !hit; x++) {
          for (var y = 0; y < b.length; y++) {
            if (a[x].team === b[y].team && a[x].from <= b[y].to && b[y].from <= a[x].to) {
              hit = a[x].team; break;
            }
          }
        }
        if (hit) { n++; shared.push(squad[i].p.n + ' + ' + squad[j].p.n + ' · ' + hit); }
      }
    }
    return { n: n, list: shared };
  }

  function countryPairs(squad) {
    var n = 0;
    for (var i = 0; i < squad.length; i++)
      for (var j = i + 1; j < squad.length; j++)
        if (squad[i].p.c && squad[i].p.c === squad[j].p.c) n++;
    return n;
  }

  function eraSpread(squad) {
    var lo = 9999, hi = 0;
    for (var i = 0; i < squad.length; i++) {
      if (squad[i].year < lo) lo = squad[i].year;
      if (squad[i].year > hi) hi = squad[i].year;
    }
    return squad.length ? hi - lo : 0;
  }

  function fitFor(weapon, slot) {
    if (!weapon || !slot) return 0;
    var v = weapon.fit[slot];
    return typeof v === 'number' ? v : 0;
  }

  // Try every pairing of 5 guns to 5 players and keep the best total fit.
  function bestAllocation(squad, weapons) {
    var idx = [], i;
    for (i = 0; i < weapons.length; i++) idx.push(i);
    var best = null, bestScore = -1e9;

    function permute(rest, acc) {
      if (!rest.length) {
        var s = 0;
        for (var k = 0; k < acc.length; k++) s += fitFor(weapons[acc[k]], squad[k].slot);
        if (s > bestScore) { bestScore = s; best = acc.slice(); }
        return;
      }
      for (var k = 0; k < rest.length; k++) {
        var next = rest.slice();
        next.splice(k, 1);
        permute(next, acc.concat(rest[k]));
      }
    }
    if (squad.length && squad.length === weapons.length) permute(idx, []);
    return { order: best, score: bestScore };
  }

  function evaluate(state) {
    var squad = state.squad.filter(Boolean);
    var weapons = state.weapons;
    var out = {
      base: 0, fit: 0, chem: 0, ovr: 0,
      bonds: { n: 0, list: [] }, countries: 0, spread: 0, alloc: null
    };
    if (!squad.length) return out;

    var sum = 0;
    for (var i = 0; i < squad.length; i++) sum += squad[i].p.ovr;
    out.base = sum / squad.length;

    // Weapon fit only counts once both sides of a pairing exist.
    if (squad.length === 5 && weapons.length === 5) {
      if (state.alloc === 'auto') {
        var a = bestAllocation(squad, weapons);
        out.alloc = a.order;
        out.fitRaw = a.score;
      } else {
        var s = 0;
        for (i = 0; i < squad.length; i++) s += fitFor(weapons[i], squad[i].slot);
        out.alloc = weapons.map(function (_, k) { return k; });
        out.fitRaw = s;
      }
      // A balanced loadout sums to roughly 10; scale that to a modest swing.
      out.fit = clamp((out.fitRaw - 10) * 0.6, -12, 9);
    }

    out.bonds = bondPairs(squad);
    out.countries = countryPairs(squad);
    out.spread = eraSpread(squad);
    var eraPenalty = Math.max(0, out.spread - 3) * 0.9;
    out.chem = clamp(out.bonds.n * 1.5 + out.countries * 0.5 - eraPenalty, -10, 12);

    out.ovr = Math.round(clamp(out.base + out.fit + out.chem, 40, 99));
    return out;
  }

  // ---------------------------------------------------------------- setup screen
  function buildOptions(hostId, list, key) {
    var host = $(hostId);
    host.innerHTML = '';
    list.forEach(function (o) {
      var b = el('button', 'opt');
      b.appendChild(el('strong', null, o.label));
      b.appendChild(el('em', null, o.desc));
      b.setAttribute('aria-pressed', setup[key] === o.id ? 'true' : 'false');
      b.addEventListener('click', function () {
        setup[key] = o.id;
        buildOptions(hostId, list, key);
      });
      host.appendChild(b);
    });
  }

  function initSetup() {
    buildOptions('opt-era', ERAS, 'era');
    buildOptions('opt-diff', DIFFS, 'diff');
    buildOptions('opt-alloc', ALLOCS, 'alloc');
    screen('setup');
  }

  // ---------------------------------------------------------------- draft
  function eraDef() {
    for (var i = 0; i < ERAS.length; i++) if (ERAS[i].id === setup.era) return ERAS[i];
    return ERAS[0];
  }

  function startRun() {
    var era = eraDef();
    var diff = DIFFS.filter(function (d) { return d.id === setup.diff; })[0];
    var pool = DATA.packs.filter(function (p) { return p.year >= era.from && p.year <= era.to; });

    run = {
      squad: [null, null, null, null, null],   // one per SLOTS index
      weapons: [],
      picks: 0,
      alloc: setup.alloc,
      rerolls: diff.rerolls,
      pool: pool,
      used: {},
      era: era
    };
    nextPack();
    screen('draft');
  }

  // Packs are drawn weighted by team strength. A flat shuffle buries the run in
  // tier-3 qualifier rosters nobody has heard of; this keeps fnatic and Astralis
  // common while still letting an obscure roster turn up now and then.
  function drawPack() {
    var pool = run.pool;
    if (!pool.length) return null;
    for (var i = 0; i < 300; i++) {
      var p = pool[Math.floor(Math.random() * pool.length)];
      var key = p.team + p.year;
      if (run.used[key]) continue;
      var weight = Math.pow(clamp((p.ovr - 52) / 47, 0, 1), 1.6);
      if (Math.random() < weight) { run.used[key] = 1; return p; }
    }
    // Fell through (small pool, or everything already seen) — take the best unused.
    var left = pool.filter(function (p) { return !run.used[p.team + p.year]; });
    if (!left.length) { run.used = {}; left = pool; }
    left.sort(function (a, b) { return b.ovr - a.ovr; });
    var chosen = left[Math.floor(Math.random() * Math.min(8, left.length))];
    run.used[chosen.team + chosen.year] = 1;
    return chosen;
  }

  function nextPack() {
    run.pack = drawPack();
    run.packWeapons = shuffled(DATA.weapons).slice(0, 5);
    renderDraft();
  }

  function slotForPlayer(p) {
    // Prefer the player's primary role, else any open slot they can fill.
    for (var i = 0; i < p.s.length; i++) {
      var s = p.s[i], k = SLOTS.indexOf(s);
      if (k >= 0 && !run.squad[k]) return k;
    }
    return -1;
  }

  function takePlayer(p) {
    var k = slotForPlayer(p);
    if (k < 0) return;
    run.squad[k] = { p: p, slot: SLOTS[k], year: run.pack.year, team: run.pack.team, event: run.pack.event };
    afterPick();
  }

  function takeWeapon(w) {
    if (run.weapons.length >= 5 || haveWeapon(w)) return;
    run.weapons.push(w);
    afterPick();
  }

  function afterPick() {
    run.picks++;
    var full = run.squad.every(Boolean) && run.weapons.length === 5;
    if (full) { showField(); return; }
    nextPack();
  }

  function needPlayers() { return run.squad.filter(Boolean).length; }

  function statChip(label, v) {
    var s = el('span');
    s.appendChild(el('i', null, label));
    s.appendChild(document.createTextNode(' ' + v));
    return s;
  }

  function playerCard(p) {
    var b = el('button', 'card');
    var openSlot = slotForPlayer(p);
    if (openSlot < 0) b.disabled = true;

    b.appendChild(el('span', 'tag', openSlot >= 0 ? SLOT_LABEL[SLOTS[openSlot]] : 'No slot'));
    var nm = el('span', 'name');
    nm.appendChild(el('span', 'flag', p.f + ' '));
    nm.appendChild(document.createTextNode(p.n));
    b.appendChild(nm);
    b.appendChild(el('span', 'big', String(p.ovr)));

    var mini = el('span', 'mini');
    mini.appendChild(statChip('RAT', p.rat));
    mini.appendChild(statChip('DUE', p.duel));
    mini.appendChild(statChip('LVL', p.lvl));
    b.appendChild(mini);

    b.title = p.n + ' — HLTV rating ' + p.hltv + ', K/D ' + p.kd +
      ', ' + p.rounds.toLocaleString() + ' rounds, best team ' + p.best;
    b.addEventListener('click', function () { if (!b.disabled) takePlayer(p); });
    return b;
  }

  function haveWeapon(w) {
    return run.weapons.some(function (x) { return x.n === w.n; });
  }

  function weaponCard(w) {
    var b = el('button', 'card wpn');
    if (run.weapons.length >= 5 || haveWeapon(w)) b.disabled = true;

    var img = new Image();
    img.src = 'img/weapons/' + w.img + '.png';
    img.alt = w.n;
    img.loading = 'lazy';
    b.appendChild(img);
    b.appendChild(el('span', 'name', w.n));

    // Show what this gun would be worth to whoever still needs a slot.
    var openSlots = [];
    for (var i = 0; i < SLOTS.length; i++) if (!run.squad[i]) openSlots.push(SLOTS[i]);
    var bestSlot = null, bestVal = -99;
    (openSlots.length ? openSlots : SLOTS).forEach(function (s) {
      var v = fitFor(w, s);
      if (v > bestVal) { bestVal = v; bestSlot = s; }
    });
    var cls = bestVal >= 3 ? 'good' : bestVal <= 0 ? 'bad' : 'mid';
    b.appendChild(el('span', 'fit ' + cls, SLOT_LABEL[bestSlot] + ' ' + (bestVal > 0 ? '+' : '') + bestVal));

    b.addEventListener('click', function () { if (!b.disabled) takeWeapon(w); });
    return b;
  }

  function renderDraft() {
    var ev = evaluate(run);

    $('team-ovr').textContent = needPlayers() ? ev.ovr : '—';

    var bd = $('breakdown');
    bd.innerHTML = '';
    function part(label, value, signed) {
      var w = el('span', signed ? (value > 0 ? 'pos' : value < 0 ? 'neg' : '') : '');
      w.appendChild(el('b', null, signed
        ? (value > 0 ? '+' : '') + value.toFixed(1)
        : Math.round(value)));
      w.appendChild(document.createTextNode(' ' + label));
      bd.appendChild(w);
    }
    part('base', ev.base, false);
    part('weapons', ev.fit, true);
    part('chemistry', ev.chem, true);
    if (ev.bonds.n) {
      var t = el('span');
      t.appendChild(el('b', null, String(ev.bonds.n)));
      t.appendChild(document.createTextNode(' played together'));
      bd.appendChild(t);
    }

    // roster strip
    var host = $('roster');
    host.innerHTML = '';
    SLOTS.forEach(function (s, i) {
      var d = el('div', 'slot' + (run.squad[i] ? ' filled' : ''));
      d.appendChild(el('div', 'role', SLOT_LABEL[s]));
      if (run.squad[i]) {
        d.appendChild(el('div', 'who', run.squad[i].p.n));
        d.appendChild(el('div', 'val', String(run.squad[i].p.ovr)));
      } else {
        d.appendChild(el('div', 'who', '—'));
      }
      host.appendChild(d);
    });

    // weapons taken so far
    var strip = $('weapon-strip');
    strip.innerHTML = '';
    for (var wi = 0; wi < 5; wi++) {
      var w = run.weapons[wi];
      var d = el('div', 'slot' + (w ? ' filled' : ''));
      if (w) {
        var wimg = new Image();
        wimg.src = 'img/weapons/' + w.img + '.png';
        wimg.alt = w.n;
        d.appendChild(wimg);
        d.appendChild(el('div', 'who', w.n));
      } else {
        d.appendChild(el('div', 'role', 'Weapon'));
        d.appendChild(el('div', 'who', '—'));
      }
      strip.appendChild(d);
    }

    var title = $('pack-title');
    title.innerHTML = '';
    title.appendChild(document.createTextNode('Pack: '));
    title.appendChild(el('b', null, run.pack.team));
    title.appendChild(document.createTextNode(' · ' + run.pack.event + ' · ' + run.pack.year));

    $('pack-progress').textContent = needPlayers() + '/5 players · ' + run.weapons.length + '/5 guns';

    var ph = $('pack-players');
    ph.innerHTML = '';
    run.pack.players.forEach(function (n) {
      var p = byName[n];
      if (p) ph.appendChild(playerCard(p));
    });

    var wh = $('pack-weapons');
    wh.innerHTML = '';
    run.packWeapons.forEach(function (w) { wh.appendChild(weaponCard(w)); });

    $('reroll-count').textContent = '(' + run.rerolls + ')';
    $('btn-reroll').disabled = run.rerolls <= 0;
    $('btn-reroll').style.opacity = run.rerolls > 0 ? '1' : '.4';

    $('draft-hint').textContent = 'One card per pack. Fill all five roles and pick five guns. ' +
      'Players who played together bring chemistry; a gun in the wrong hands costs you.';
  }

  // ---------------------------------------------------------------- field
  function showField() {
    var ev = evaluate(run);
    run.eval = ev;

    // Pick a real tournament field from the chosen era.
    var fields = DATA.fields.filter(function (f) {
      return f.year >= run.era.from && f.year <= run.era.to;
    });
    if (!fields.length) fields = DATA.fields;
    var field = pick(fields);

    var rivals = field.teams.slice(0, 15).map(function (t) {
      return { name: t.n, ovr: t.ovr, you: false };
    });
    run.field = field;
    run.teams = rivals.concat([{ name: 'Your Team', ovr: ev.ovr, you: true }]);
    run.teams.sort(function (a, b) { return b.ovr - a.ovr; });

    $('field-title').textContent = field.name;
    var rank = run.teams.findIndex(function (t) { return t.you; }) + 1;
    $('field-sub').textContent = field.year + ' · 16 teams · you are seeded ' + rank +
      (rank > 8 ? ' — the bracket does not care about your feelings.' : '.');

    var host = $('field-list');
    host.innerHTML = '';
    run.teams.forEach(function (t, i) {
      var r = el('div', 'row' + (t.you ? ' you' : ''));
      r.appendChild(el('span', 'seed', String(i + 1)));
      r.appendChild(el('span', 'nm', t.name));
      r.appendChild(el('span', 'val', String(t.ovr)));
      host.appendChild(r);
    });

    screen('field');
  }

  // ---------------------------------------------------------------- simulation
  //
  // One map is 24 rounds max (MR12): first to 13, overtime if it reaches 12-12.
  // Each round is a weighted coin from the rating gap, clamped so that neither
  // a mismatch nor an upset ever becomes a certainty.

  // Round win probability from the rating gap. The scale is deliberately wide:
  // a round is a small event, and 13 of them compound hard. At /25 a five-point
  // edge won 88% of maps, which is nothing like real Counter-Strike — the better
  // team wins most nights, not every night. At /55 a five-point edge is ~65%.
  var PROB_SCALE = 55;

  function roundProb(a, b) {
    return clamp(1 / (1 + Math.pow(10, (b - a) / PROB_SCALE)), 0.22, 0.78);
  }

  function playMap(a, b) {
    var p = roundProb(a.ovr, b.ovr);
    var sa = 0, sb = 0;
    while (true) {
      if (Math.random() < p) sa++; else sb++;
      if (sa >= 13 && sa - sb >= 2) break;
      if (sb >= 13 && sb - sa >= 2) break;
      if (sa >= 12 && sb >= 12 && Math.abs(sa - sb) >= 2) break;
      if (sa + sb > 60) break; // safety valve
    }
    return { a: sa, b: sb };
  }

  function playSeries(a, b, bestOf) {
    var need = Math.ceil(bestOf / 2);
    var maps = [], wa = 0, wb = 0;
    while (wa < need && wb < need) {
      var m = playMap(a, b);
      maps.push(m);
      if (m.a > m.b) wa++; else wb++;
    }
    return { a: a, b: b, wa: wa, wb: wb, maps: maps, winner: wa > wb ? a : b, loser: wa > wb ? b : a };
  }

  function swissStage(teams) {
    var st = teams.map(function (t, i) {
      return { team: t, w: 0, l: 0, seed: i, opps: [], done: false };
    });
    var rounds = [];

    for (var r = 0; r < 6; r++) {
      var live = st.filter(function (s) { return s.w < 3 && s.l < 3; });
      if (!live.length) break;

      // Buchholz: strength of the opponents you have already faced.
      live.forEach(function (s) {
        s.buch = s.opps.reduce(function (acc, o) { return acc + (o.w - o.l); }, 0);
      });

      var groups = {};
      live.forEach(function (s) {
        var k = s.w + '-' + s.l;
        (groups[k] = groups[k] || []).push(s);
      });

      var matches = [];
      Object.keys(groups).forEach(function (k) {
        var g = groups[k].sort(function (x, y) {
          return (y.buch - x.buch) || (x.seed - y.seed);
        });
        // High seed plays low seed, as the real format does.
        while (g.length >= 2) {
          var hi = g.shift(), lo = g.pop();
          var bestOf = (hi.w === 2 || hi.l === 2 || lo.w === 2 || lo.l === 2) ? 3 : 1;
          var res = playSeries(hi.team, lo.team, bestOf);
          var hiWon = res.winner === hi.team;
          (hiWon ? hi : lo).w++;
          (hiWon ? lo : hi).l++;
          hi.opps.push(lo); lo.opps.push(hi);
          matches.push({ res: res, bestOf: bestOf });
        }
      });
      if (matches.length) rounds.push(matches);
    }

    st.sort(function (a, b) { return (b.w - a.w) || (a.l - b.l) || (a.seed - b.seed); });
    return { rounds: rounds, standings: st, advanced: st.filter(function (s) { return s.w >= 3; }).slice(0, 8) };
  }

  function playoffs(seeds) {
    var stages = [];
    var alive = seeds.slice();
    var names = ['Quarter-finals', 'Semi-finals', 'Grand Final'];
    var n = 0;
    while (alive.length > 1) {
      var matches = [], next = [];
      for (var i = 0; i < alive.length / 2; i++) {
        var a = alive[i], b = alive[alive.length - 1 - i];
        var res = playSeries(a, b, 3);
        matches.push({ res: res, bestOf: 3 });
        next.push(res.winner);
      }
      stages.push({ name: names[n] || 'Round ' + (n + 1), matches: matches });
      alive = next;
      n++;
    }
    return { stages: stages, champion: alive[0] };
  }

  function runTournament() {
    var swiss = swissStage(run.teams);
    var seeds = swiss.advanced.map(function (s) { return s.team; });
    var po = seeds.length >= 2 ? playoffs(seeds) : { stages: [], champion: seeds[0] };

    // Everything the player's own team was involved in, for the verdict.
    var you = null, mapsLost = 0, seriesLost = 0, played = 0, perfectMaps = 0;
    function scan(m) {
      var r = m.res;
      if (!r.a.you && !r.b.you) return;
      played++;
      var mine = r.a.you ? 'a' : 'b', theirs = mine === 'a' ? 'b' : 'a';
      r.maps.forEach(function (mp) {
        if (mp[mine] > mp[theirs]) { if (mp[theirs] === 0) perfectMaps++; }
        else mapsLost++;
      });
      if (r.winner.you !== true) seriesLost++;
    }
    swiss.rounds.forEach(function (rd) { rd.forEach(scan); });
    po.stages.forEach(function (s) { s.matches.forEach(scan); });

    you = swiss.standings.filter(function (s) { return s.team.you; })[0];
    var champion = po.champion || null;

    run.result = {
      swiss: swiss,
      po: po,
      champion: champion,
      youAdvanced: !!(you && you.w >= 3),
      youRecord: you ? you.w + '-' + you.l : '',
      mapsLost: mapsLost,
      seriesLost: seriesLost,
      perfectMaps: perfectMaps,
      played: played,
      champ: champion && champion.you === true,
      flawless: champion && champion.you === true && mapsLost === 0
    };
  }

  // ---------------------------------------------------------------- sim rendering
  var simTimers = [];
  function laterStep(fn, ms) {
    var id = setTimeout(fn, ms);
    simTimers.push(id);
    return id;
  }
  function clearSim() {
    simTimers.forEach(clearTimeout);
    simTimers = [];
  }

  function matchRow(m) {
    var r = m.res;
    var row = el('div', 'match' + (r.a.you || r.b.you ? ' you' : ''));
    var aWon = r.winner === r.a;
    var a = el('span', 'a ' + (aWon ? 'win' : 'lose'), r.a.name);
    var b = el('span', 'b ' + (aWon ? 'lose' : 'win'), r.b.name);
    var score = el('span', 'score', r.wa + ' – ' + r.wb);
    row.appendChild(a);
    row.appendChild(score);
    row.appendChild(b);

    var detail = r.maps.map(function (mp) { return mp.a + '-' + mp.b; }).join('  ·  ');
    var d = el('span', 'maps', detail);
    var perfect = r.maps.some(function (mp) { return mp.a === 0 || mp.b === 0; });
    if (perfect) d.className = 'maps perfect';
    row.appendChild(d);
    return row;
  }

  function showSim() {
    runTournament();
    screen('sim');
    var body = $('sim-body');
    body.innerHTML = '';
    $('sim-title').textContent = run.field.name;
    $('sim-sub').textContent = 'Legends Stage — three wins to advance, three losses and you are out.';

    var steps = [];
    run.result.swiss.rounds.forEach(function (rd, i) {
      steps.push({ label: 'Swiss round ' + (i + 1), matches: rd });
    });
    run.result.po.stages.forEach(function (s) {
      steps.push({ label: s.name, matches: s.matches });
    });

    var i = 0;
    function step() {
      if (i >= steps.length) { laterStep(showResult, 500); return; }
      var s = steps[i++];
      body.appendChild(el('h3', 'stage-label', s.label));
      s.matches.forEach(function (m, k) {
        laterStep(function () { body.appendChild(matchRow(m)); }, k * 90);
      });
      laterStep(step, s.matches.length * 90 + 420);
      window.scrollTo(0, document.body.scrollHeight);
    }
    step();
  }

  function skipSim() {
    clearSim();
    showResult();
  }

  // ---------------------------------------------------------------- result
  function showResult() {
    clearSim();
    var res = run.result;
    var banner = $('result-banner');
    banner.innerHTML = '';

    var verdict, sub;
    if (res.flawless) {
      verdict = el('div', 'verdict flawless', '13-0');
      sub = 'Champions without dropping a single map. This is the run the game is named after.';
    } else if (res.champ) {
      verdict = el('div', 'verdict champ', 'CHAMPIONS');
      sub = 'You won ' + run.field.name + ' — but dropped ' + res.mapsLost +
        (res.mapsLost === 1 ? ' map' : ' maps') + ' on the way. Not flawless.';
    } else if (res.youAdvanced) {
      verdict = el('div', 'verdict out', 'Knocked out');
      sub = 'Through the Legends Stage at ' + res.youRecord + ', then beaten in the bracket.';
    } else {
      verdict = el('div', 'verdict out', 'Eliminated');
      sub = 'Out of the Legends Stage at ' + res.youRecord + '. No bracket, no story.';
    }
    banner.appendChild(verdict);
    banner.appendChild(el('div', 'verdict-sub', sub));

    var body = $('result-body');
    body.innerHTML = '';

    if (res.champion) {
      var champ = el('div', 'summary');
      champ.appendChild(el('h3', null, 'Champion'));
      var c = el('div', 'row' + (res.champion.you ? ' you' : ''));
      c.appendChild(el('span', 'seed', '🏆'));
      c.appendChild(el('span', 'nm', res.champion.name));
      c.appendChild(el('span', 'val', String(res.champion.ovr)));
      champ.appendChild(c);
      body.appendChild(champ);
    }

    // your lineup
    var line = el('div', 'summary');
    line.appendChild(el('h3', null, 'Your five'));
    var lw = el('div', 'lineup');
    var order = run.eval.alloc;
    run.squad.forEach(function (s, i) {
      if (!s) return;
      var row = el('div', 'lineup-row');
      // evaluate() works on the compacted squad, which — once all five slots are
      // filled — is exactly SLOTS order, so alloc[i] is this player's gun.
      var w = (order && order[i] != null) ? run.weapons[order[i]] : run.weapons[i];
      if (w) {
        var img = new Image();
        img.src = 'img/weapons/' + w.img + '.png';
        img.alt = w.n;
        row.appendChild(img);
      } else {
        row.appendChild(el('span'));
      }
      var nm = el('span');
      nm.appendChild(el('span', 'role', SLOT_LABEL[s.slot] + '  '));
      nm.appendChild(document.createTextNode(s.p.f + ' ' + s.p.n));
      row.appendChild(nm);
      row.appendChild(el('span', 'role', s.team + ' ' + s.year));
      row.appendChild(el('span', 'val', String(s.p.ovr)));
      lw.appendChild(row);
    });
    line.appendChild(lw);
    body.appendChild(line);

    // run facts
    var facts = el('div', 'summary');
    facts.appendChild(el('h3', null, 'The run'));
    [
      ['Team OVR', String(run.eval.ovr)],
      ['Legends Stage', res.youRecord],
      ['Maps dropped', String(res.mapsLost)],
      ['13-0 maps you won', String(res.perfectMaps)],
      ['Chemistry pairs', String(run.eval.bonds.n)]
    ].forEach(function (kv) {
      var r = el('div', 'record');
      r.appendChild(el('span', null, kv[0]));
      r.appendChild(el('span'));
      r.appendChild(el('span', 'val', kv[1]));
      facts.appendChild(r);
    });
    if (run.eval.bonds.list.length) {
      var note = el('p', 'hint', 'Played together: ' + run.eval.bonds.list.join(' · '));
      facts.appendChild(note);
    }
    body.appendChild(facts);

    // final standings
    var st = el('div', 'summary');
    st.appendChild(el('h3', null, 'Legends Stage standings'));
    res.swiss.standings.forEach(function (s) {
      var r = el('div', 'record' + (s.team.you ? ' you' : ''));
      r.appendChild(el('span', null, s.team.name));
      r.appendChild(el('span', 'st ' + (s.w >= 3 ? 'adv' : 'out'), s.w >= 3 ? 'ADVANCED' : 'OUT'));
      r.appendChild(el('span', null, s.w + '-' + s.l));
      st.appendChild(r);
    });
    body.appendChild(st);

    screen('result');
  }

  // ---------------------------------------------------------------- wiring
  function wire() {
    $('btn-start').addEventListener('click', startRun);
    $('btn-sim').addEventListener('click', showSim);
    $('btn-skip').addEventListener('click', skipSim);
    $('btn-again').addEventListener('click', initSetup);
    $('btn-abandon').addEventListener('click', initSetup);
    $('btn-reroll').addEventListener('click', function () {
      if (run.rerolls <= 0) return;
      run.rerolls--;
      nextPack();
    });
    $('btn-about').addEventListener('click', function () { $('about').hidden = false; });
    $('btn-about-close').addEventListener('click', function () { $('about').hidden = true; });
  }

  function boot() {
    var files = ['players', 'weapons', 'packs', 'fields'];
    Promise.all(files.map(function (f) {
      return fetch('data/' + f + '.json').then(function (r) {
        if (!r.ok) throw new Error(f + ': ' + r.status);
        return r.json();
      });
    })).then(function (loaded) {
      files.forEach(function (f, i) { DATA[f] = loaded[i]; });
      DATA.players.forEach(function (p) { byName[p.n] = p; });
      $('boot').style.display = 'none';
      wire();
      initSetup();
      window.__game = {
        DATA: DATA,
        get run() { return run; },
        evaluate: evaluate,
        playMap: playMap,
        // Balance probe: how does a team of a given OVR actually fare over n Majors?
        testRun: function (ovr, n, fieldName) {
          var out = { runs: n, champ: 0, flawless: 0, advanced: 0, mapsLost: 0, perfect: 0 };
          var saved = run;
          for (var i = 0; i < n; i++) {
            var fields = DATA.fields.filter(function (f) {
              return !fieldName || f.name === fieldName;
            });
            var field = fields[Math.floor(Math.random() * fields.length)];
            var teams = field.teams.slice(0, 15).map(function (t) {
              return { name: t.n, ovr: t.ovr, you: false };
            });
            teams.push({ name: 'Your Team', ovr: ovr, you: true });
            teams.sort(function (a, b) { return b.ovr - a.ovr; });
            run = { teams: teams, field: field };
            runTournament();
            var r = run.result;
            if (r.champ) out.champ++;
            if (r.flawless) out.flawless++;
            if (r.youAdvanced) out.advanced++;
            out.mapsLost += r.mapsLost;
            out.perfect += r.perfectMaps;
          }
          run = saved;
          return {
            ovr: ovr,
            advanced: (100 * out.advanced / n).toFixed(1) + '%',
            champion: (100 * out.champ / n).toFixed(1) + '%',
            flawless: (100 * out.flawless / n).toFixed(2) + '%',
            avgMapsLost: (out.mapsLost / n).toFixed(1),
            avg13_0maps: (out.perfect / n).toFixed(2)
          };
        }
      };
    }).catch(function (e) {
      $('boot').textContent = 'Could not load the data: ' + e.message;
    });
  }

  boot();
})();
