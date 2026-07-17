// ==UserScript==
// @name         Fantasy Analyzer — Draft Bridge (ESPN)
// @namespace    https://github.com/andredagoat23/fantasy-analyzer
// @version      0.1.0
// @description  Forwards your live ESPN draft picks to the Fantasy Analyzer app (via a Firebase mailbox).
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

  // These selectors find the pick rows in ESPN's draft room. ESPN's class names shift,
  // so we match loosely — run  FAB.dom()  in the console on a mock draft and we'll tune these.
  const SEL = {
    row: '[class*="pick"]',                 // each pick row / card
    player: '[class*="player"], a[href*="playerId"], a',  // player-name element inside a row
    team: '[class*="team"], [class*="owner"]',            // drafting-team element inside a row
  };

  const log = (...a) => DEBUG && console.log('%c[FA-Bridge]', 'color:#E2725B;font-weight:bold', ...a);

  // ---- state ----
  let picks = [];       // [{player, team, mine?}] in draft order
  let lastPayload = ''; // dedupe: only PUT when the pick set actually changes

  // ---- send the current picks to the Firebase mailbox ----
  // A PUT triggers a CORS preflight, which Firebase's REST API answers for the espn.com
  // origin (Access-Control-Allow-Methods includes PUT), so the write goes through. We skip
  // custom headers so the browser doesn't have to negotiate extra ones.
  function push() {
    const payload = JSON.stringify({ picks });
    if (payload === lastPayload) return;      // unchanged — skip
    lastPayload = payload;
    fetch(BRIDGE_URL + '/draft.json', { method: 'PUT', body: payload })
      .then((r) => { if (!r.ok) throw new Error(r.status); log('sent', picks.length, 'picks'); hud(`🟢 ${picks.length} picks sent`); })
      .catch((e) => { log('send FAILED', e); hud('🔴 send failed — check the URL'); });
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
    if (!/pick|player|draft|member|roster|team/i.test(data)) return;
    wsSeen.push(data);
    if (wsSeen.length > 40) wsSeen.shift();
    log('WS message', data.slice(0, 500));
    // TODO (tune live): once we see the real pick shape, build `picks` from these messages
    // and call push() — a socket feed is more reliable than scraping the DOM.
  }

  // Only scrape inside an actual draft room — otherwise the loose selectors pick up junk
  // (nav labels like "All") on regular ESPN pages and spam the mailbox.
  const inDraftRoom = () => /draft/i.test(location.href);

  // ---- DOM scraper (works immediately; tuned live) ---------------------------
  function scrape() {
    const out = [];
    document.querySelectorAll(SEL.row).forEach((row) => {
      const p = row.querySelector(SEL.player);
      const t = row.querySelector(SEL.team);
      const player = p && p.textContent.trim();
      const team = t && t.textContent.trim();
      // player names are "First Last" — require a space to skip stray one-word UI text
      if (player && player.includes(' ')) {
        const pick = { player, team: team || '' };
        if (MY_TEAM && team === MY_TEAM) pick.mine = true;
        out.push(pick);
      }
    });
    return out;
  }

  // ---- main loop -------------------------------------------------------------
  setInterval(() => {
    if (!inDraftRoom()) { hud('idle — open your draft room'); return; }
    try {
      const found = scrape();
      if (found.length) { picks = found; push(); }
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
    // Dump candidate pick rows so we can lock the SEL selectors on a mock draft.
    dom() {
      const rows = document.querySelectorAll(SEL.row);
      console.log('[FA-Bridge] SEL.row matched', rows.length, 'elements. First 3:');
      [...rows].slice(0, 3).forEach((r, i) => console.log(i, r.className, r.outerHTML.slice(0, 600)));
      console.log('current scrape() ->', scrape());
    },
    ws() { console.log('[FA-Bridge] last WS messages:', wsSeen); return wsSeen; },
    picks() { return picks; },
    // Fire a single fake pick to prove the pipe end-to-end (watch it hit the app).
    test() { picks = [{ player: 'Bijan Robinson', team: MY_TEAM || 'Test Team', mine: true }]; lastPayload = ''; push(); },
    // Clear the mailbox.
    clear() { picks = []; lastPayload = ''; fetch(BRIDGE_URL + '/draft.json', { method: 'DELETE' }); },
  };

  log('loaded. Commands: FAB.test(), FAB.dom(), FAB.ws(), FAB.picks(), FAB.clear()');
})();
