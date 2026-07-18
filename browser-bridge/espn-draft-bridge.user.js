// ==UserScript==
// @name         Fantasy Analyzer — Draft Bridge (ESPN)
// @namespace    https://github.com/andredagoat23/fantasy-analyzer
// @version      0.3.0
// @description  Forwards your live ESPN draft picks + league shape to the Fantasy Analyzer app (via a Firebase mailbox).
// @author       Fantasy Analyzer
// @match        https://*.espn.com/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // ============================ CONFIG — edit these ============================
  // Your Firebase Realtime Database URL (the mailbox the app reads).
  const BRIDGE_URL = 'https://fantasy-analyzer-3741d-default-rtdb.firebaseio.com';
  // OPTIONAL: your EXACT ESPN team name -> auto-marks your own picks as "mine".
  // Leave "" and just choose your team in the app instead.
  const MY_TEAM = '';
  // How often (ms) to scan the draft room for new picks.
  const POLL_MS = 2000;
  // true = print discovery info to the browser console (F12). Turn off once it's tuned.
  const DEBUG = true;
  // ============================================================================

  // Locked against ESPN's live draft room (mock-draft capture, 2026). The "Pick History" grid is
  // a virtualized React fixed-data-table: one table per round, each row = 6 cells in a fixed order
  // [pick #, player, fantasy owner, 2025 pts, proj pts, rank]. The player name lives in an <a> in
  // cell 1 — reading that anchor gives a clean "First Last" with none of the NFL-team / position /
  // injury-tag text that's mashed into the cell.
  const SEL = {
    round: '.pick-history-table',                // one table per drafted round
    row: '.public_fixedDataTableRow_main',       // each pick row (plus a header row we skip)
    header: 'public_fixedDataTable_header',      // class on the header row -> skip it
    cell: '.public_fixedDataTableCell_main',     // the 6 cells within a row
  };

  const log = (...a) => DEBUG && console.log('%c[FA-Bridge]', 'color:#E2725B;font-weight:bold', ...a);

  // ---- state ----
  let meta = null;        // {teams, slot, myTeam, myPicks} read once from ESPN's API (see fetchMeta)
  let picks = [];         // [{pick, player, team, mine?}] in draft order (sent to the mailbox)
  const seen = new Map(); // pick# -> pick. Accumulate-only: ESPN's grid is virtualized, so a round
  //                         that scrolls out of view un-renders. Keeping every pick we've ever seen
  //                         means a de-rendered round can't "un-draft" players on the board.
  let lastPayload = '';   // dedupe: only PUT when the pick set actually changes

  // ---- send the current picks to the Firebase mailbox ----
  // A PUT triggers a CORS preflight, which Firebase's REST API answers for the espn.com
  // origin (Access-Control-Allow-Methods includes PUT), so the write goes through. We skip
  // custom headers so the browser doesn't have to negotiate extra ones.
  function push() {
    const body = { picks };
    if (meta) body.meta = meta;               // league shape (team count, your seat + pick numbers)
    const payload = JSON.stringify(body);
    if (payload === lastPayload) return;      // unchanged — skip
    lastPayload = payload;
    fetch(BRIDGE_URL + '/draft.json', { method: 'PUT', body: payload })
      .then((r) => { if (!r.ok) throw new Error(r.status); log('sent', picks.length, 'picks'); hud(`🟢 ${picks.length} picks sent`); })
      .catch((e) => { log('send FAILED', e); hud('🔴 send failed — check the URL'); });
  }

  // ---- league shape from ESPN's own API (read once) --------------------------
  // Your browser is authenticated with ESPN, so we can read the league config directly — no
  // scraping. `mTeam` gives the team names/count; `mDraftDetail` gives the full pick order (which
  // teamId owns each overall pick), so we can hand the app YOUR exact pick numbers for whatever
  // draft order the league uses (snake, 3rd-round-reversal, linear, …) instead of guessing.
  async function fetchMeta() {
    const lg = (location.href.match(/leagueId=(\d+)/) || [])[1];
    const sn = (location.href.match(/seasonId=(\d+)/) || [, '2026'])[1];
    const tid = parseInt((location.href.match(/teamId=(\d+)/) || [])[1], 10);
    if (!lg) return null;                      // not on a league draft URL
    const base = `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${sn}/segments/0/leagues/${lg}`;
    const j = await fetch(`${base}?view=mTeam&view=mDraftDetail`, { credentials: 'include' }).then((r) => r.json());
    const teamsArr = j.teams || [];
    if (!teamsArr.length) return null;         // API not ready yet — retry next tick
    const mineTeam = teamsArr.find((t) => t.id === tid);
    const myTeam = mineTeam ? (mineTeam.name || `${mineTeam.location || ''} ${mineTeam.nickname || ''}`).trim() : '';
    const allPicks = (j.draftDetail || {}).picks || [];
    const myPicks = allPicks.filter((p) => p.teamId === tid)
                            .map((p) => p.overallPickNumber).sort((a, b) => a - b);
    const r1 = allPicks.find((p) => p.teamId === tid && p.roundId === 1);
    return { teams: teamsArr.length, slot: r1 ? r1.roundPickNumber : undefined, myTeam, myPicks };
  }

  // ---- WebSocket sniffer (discovery) -----------------------------------------
  // ESPN pushes draft events over a socket. We wrap WebSocket so we can SEE the real
  // message shape on a mock draft, then wire a rock-solid parser here (no DOM needed).
  const OrigWS = window.WebSocket;
  if (OrigWS) {
    const Wrapped = function (url, protocols) {
      const ws = protocols ? new OrigWS(url, protocols) : new OrigWS(url);
      try { ws.addEventListener('message', (ev) => onSocket(String(url), ev.data)); } catch (e) {}
      log('WebSocket opened →', url);
      return ws;
    };
    Wrapped.prototype = OrigWS.prototype;
    Wrapped.OPEN = OrigWS.OPEN; Wrapped.CLOSED = OrigWS.CLOSED;
    Wrapped.CONNECTING = OrigWS.CONNECTING; Wrapped.CLOSING = OrigWS.CLOSING;
    window.WebSocket = Wrapped;
  }
  const wsSeen = [];
  function onSocket(url, data) {
    if (typeof data !== 'string') return;
    // Capture ALL text frames (capped). ESPN's draft socket speaks a terse token protocol
    // ("AUTODRAFT 1 false", and pick events that DON'T contain the words pick/player/etc.), so an
    // earlier keyword filter here silently dropped the real pick messages. No filter = we see them.
    wsSeen.push(data);
    if (wsSeen.length > 60) wsSeen.shift();
    log('WS message', data.slice(0, 500));
    // TODO (future): the DOM scraper below is the live source today. If the socket turns out to
    // carry clean pick events, build `picks` from them here — a feed beats scraping.
  }

  // Only scrape inside an actual draft room — the Pick History grid only exists there, and this
  // keeps us off regular ESPN pages entirely.
  const inDraftRoom = () => /draft/i.test(location.href);

  // ---- DOM scraper (locked to the Pick History grid) -------------------------
  // Reads every rendered pick row into {pick, player, team}. Player = the anchor in cell 1
  // (clean name); team = cell 2 (the fantasy owner, what identifies YOUR picks).
  function scrape() {
    const out = [];
    document.querySelectorAll(`${SEL.round} ${SEL.row}`).forEach((row) => {
      if (row.className.includes(SEL.header)) return;      // "Pick Player Team…" header row
      const cells = row.querySelectorAll(SEL.cell);
      if (cells.length < 3) return;
      const pick = parseInt(cells[0].textContent.trim(), 10);
      if (!pick) return;                                   // not a real data row
      const a = cells[1].querySelector('a');
      const player = (a ? a.textContent : cells[1].textContent).trim();
      const team = cells[2].textContent.trim();            // fantasy owner (not the NFL team)
      if (player) {
        const p = { pick, player, team };
        if (MY_TEAM && team === MY_TEAM) p.mine = true;
        out.push(p);
      }
    });
    return out;
  }

  // ---- main loop -------------------------------------------------------------
  let metaTries = 0;
  setInterval(() => {
    if (!inDraftRoom()) { hud('idle — open your draft room'); return; }
    // Read the league shape once (retry a few times in case the API isn't ready at page load).
    if (!meta && metaTries < 10) {
      metaTries += 1;
      fetchMeta().then((m) => { if (m) { meta = m; lastPayload = ''; log('league shape', m); push(); } })
                 .catch((e) => log('meta fetch failed', e));
    }
    try {
      const found = scrape();
      if (found.length) {
        found.forEach((p) => seen.set(p.pick, p));         // accumulate; a de-rendered round can't drop picks
        picks = [...seen.values()].sort((a, b) => a.pick - b.pick);
        push();
      }
    } catch (e) { log('scrape error', e); }
  }, POLL_MS);

  // ---- floating status badge -------------------------------------------------
  let hudEl = null;
  function hud(text) {
    if (!document.body) return;
    if (!hudEl) {
      hudEl = document.createElement('div');
      hudEl.style.cssText = 'position:fixed;bottom:14px;right:14px;z-index:2147483647;' +
        'background:#191E26;color:#E6EDF3;border:1px solid #2A313C;border-radius:10px;' +
        'padding:8px 12px;font:600 12px/1.2 system-ui,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.45)';
      document.body.appendChild(hudEl);
    }
    hudEl.textContent = 'FA Bridge · ' + text;
  }
  const bootHud = () => hud('waiting for picks…');
  if (document.body) bootHud(); else window.addEventListener('DOMContentLoaded', bootHud);

  // ---- console helpers for tuning & testing ----------------------------------
  window.FAB = {
    // Sanity-check the Pick History grid and what scrape() pulls from it.
    dom() {
      const rounds = document.querySelectorAll(SEL.round);
      const rows = document.querySelectorAll(`${SEL.round} ${SEL.row}`);
      console.log('[FA-Bridge]', rounds.length, 'round tables,', rows.length, 'rows. scrape() ->');
      console.table(scrape());
    },
    ws() { console.log('[FA-Bridge] last WS messages:', wsSeen); return wsSeen; },
    picks() { return picks; },
    meta() { console.log('[FA-Bridge] league shape:', meta); return meta; },
    // Fire a single fake pick to prove the pipe end-to-end (watch it hit the app).
    test() { picks = [{ pick: 1, player: 'Bijan Robinson', team: MY_TEAM || 'Test Team', mine: true }]; lastPayload = ''; push(); },
    // Clear the mailbox AND the local state (use between mock drafts — re-reads the league shape).
    clear() { picks = []; seen.clear(); meta = null; metaTries = 0; lastPayload = ''; fetch(BRIDGE_URL + '/draft.json', { method: 'DELETE' }); },
  };

  log('loaded. Commands: FAB.test(), FAB.dom(), FAB.ws(), FAB.picks(), FAB.meta(), FAB.clear()');
})();
