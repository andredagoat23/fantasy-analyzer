import streamlit as st

import advisor
import auth
import config_store

SITES = ["ESPN", "Sleeper", "Yahoo", "Other"]
SCORING = ["PPR", "Half-PPR", "Standard", "Custom"]
RISK_LEVELS = ["Full send", "Aggressive", "Balanced", "Cautious", "Safe"]

# ESPN live-sync status is read from secrets — cookies are never entered in the UI.
try:
    espn_ready = bool(dict(st.secrets.get("espn", {})).get("league_id"))
except Exception:
    espn_ready = False

# --- Top action bar: Save + Enter the draft, immediately visible at the top ---
a1, a2 = st.columns(2)
with a1:
    if st.button("Save changes", icon=":material/save:", width="stretch"):
        config_store.save(auth.current_user_key())
        st.toast("Setup saved.", icon=":material/check_circle:")
with a2:
    if st.button("Enter the draft", type="primary", icon=":material/sports_football:", width="stretch"):
        config_store.save(auth.current_user_key())
        st.switch_page("app_pages/draft.py")

st.markdown("#### :material/tune: Pre-draft setup")
st.caption("Click a card to open that block and edit it.")

# ---- Current state for the cards ----
_name = (st.session_state.get("league_name") or "").strip()
_teams = int(st.session_state.get("teams", 12))
_slot = int(st.session_state.get("slot", 4))
_site = st.session_state.get("site") or "—"
if _site == "Other":
    _site = (st.session_state.get("site_other") or "").strip() or "Other"
_scoring = st.session_state.get("scoring") or "PPR"
_custom_done = _scoring == "Custom" and bool(st.session_state.get("scoring_parsed"))
_strategy = (st.session_state.get("strategy") or "").strip()
_league_id = (st.session_state.get("league_id") or "").strip()

if _scoring == "Custom":
    _sc_badge = ":green-badge[deciphered]" if _custom_done else ":orange-badge[needs decipher]"
    _sc_sum = "Custom scoring" + (" · AI-deciphered" if _custom_done else " · paste & decipher")
else:
    _sc_badge, _sc_sum = ":green-badge[set]", f"{_scoring} scoring"
if espn_ready:
    _cn_badge, _cn_sum = ":green-badge[connected]", "ESPN live sync connected"
elif _league_id:
    _cn_badge, _cn_sum = ":blue-badge[manual]", f"League ID {_league_id} · manual tracking"
else:
    _cn_badge, _cn_sum = ":gray-badge[optional]", "Not connected · manual tracking"

CARDS = {
    "League":     (":material/emoji_events:", ":green-badge[set]" if _name else ":gray-badge[no name]",
                   f"{_name or 'Unnamed league'} · {_teams} teams · pick {_slot} · {_site}"),
    "Connection": (":material/link:", _cn_badge, _cn_sum),
    "Scoring":    (":material/functions:", _sc_badge, _sc_sum),
    "Strategy":   (":material/strategy:", ":green-badge[set]" if _strategy else ":gray-badge[empty]",
                   (_strategy[:58] + "…") if len(_strategy) > 58
                   else (_strategy or "No strategy yet · uses your risk default")),
}


def _open(name):
    st.session_state.active_section = name


active = st.session_state.get("active_section", "League")
names = list(CARDS)
for _row in (names[:2], names[2:]):                # 2x2 grid of clickable cards
    cols = st.columns(2)
    for col, name in zip(cols, _row):
        icon, badge, summary = CARDS[name]
        with col:
            with st.container(border=True):
                st.button(name, icon=icon, key=f"card_{name}", width="stretch",
                          type="primary" if active == name else "secondary",
                          on_click=_open, args=(name,))
                st.markdown(badge)
                st.caption(summary)

# ---- The open block (only the active section renders its widgets; app.py keeps the rest alive) ----
with st.container(border=True):
    if active == "League":
        st.text_input("League name", key="league_name", placeholder="e.g. The Sunday Scaries")
        st.segmented_control("Drafting site", SITES, key="site")
        if st.session_state.get("site") == "Other":
            st.text_input("Which site?", key="site_other",
                          placeholder="e.g. NFL.com, CBS, RTSports, Fantrax")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("League size (teams)", 2, 20, key="teams")
        with c2:
            _tm = int(st.session_state.get("teams", 12))
            if int(st.session_state.get("slot", 1)) > _tm:      # keep slot within the league
                st.session_state["slot"] = _tm
            st.number_input("Your draft slot", 1, _tm, key="slot",
                            help="Your seat in the snake order. Caps at your league size.")

    elif active == "Connection":
        st.text_input("League ID", key="league_id",
                      help="Found in your league URL. For live ESPN sync, also add it to secrets.")
        if espn_ready:
            st.success("ESPN live sync is connected — picks auto-track during your draft.",
                       icon=":material/wifi:")
        else:
            st.info("ESPN live sync isn't configured, so you'll track picks manually on the board. "
                    "Add an `[espn]` block to secrets to enable auto-tracking.",
                    icon=":material/wifi_off:")

    elif active == "Scoring":
        scoring = st.segmented_control("League scoring", SCORING, key="scoring")
        if scoring == "Custom":
            st.caption("Paste your league's exact scoring rules and let AI translate them into a clean "
                       "breakdown the advisor will use. (This informs the advisor — the board's rankings "
                       "stay as computed in the pipeline.)")
            raw = st.text_area("Your scoring settings", key="scoring_custom", height=150,
                               placeholder="Paste from your league settings, e.g. Passing TD 4, INT -2, "
                                           "Rush/Rec TD 6, Reception 0.5, 100+ rush/rec yds +3 …")
            try:
                _api_key = st.secrets.get("ANTHROPIC_API_KEY")
            except Exception:
                _api_key = None
            go = st.button("Decipher with AI", icon=":material/auto_awesome:", type="primary",
                           disabled=not (_api_key and (raw or "").strip()))
            if not _api_key:
                st.caption("Add `ANTHROPIC_API_KEY` to secrets to enable AI parsing.")
            if go:
                with st.spinner("Deciphering your scoring…"):
                    try:
                        parsed = advisor.parse_scoring(advisor.get_client(_api_key), raw)
                    except Exception as e:
                        parsed = None
                        st.error(f"Couldn't parse that: {e}", icon=":material/error:")
                if parsed:
                    st.session_state["scoring_parsed"] = parsed
                    config_store.save(auth.current_user_key())
                    st.toast("Scoring deciphered and saved.", icon=":material/check_circle:")
            if st.session_state.get("scoring_parsed"):
                st.markdown("**Deciphered scoring** — this is what the advisor will use:")
                st.success(st.session_state["scoring_parsed"], icon=":material/functions:")
        else:
            st.caption("Tells the advisor how your league scores. Choose **Custom** to paste and "
                       "AI-parse your exact settings.")

    elif active == "Strategy":
        st.text_area("Your draft strategy", key="strategy",
                     placeholder="e.g. Hero RB — lock one elite RB early, then hammer WR. "
                                 "Wait on QB until round 8+. Stream D/ST and K late.")
        st.caption("Example: *\"Hero RB — one elite RB early, then hammer WR through round 6. "
                   "Wait on QB/TE, stream D/ST + K last.\"*  ·  Not sure? Leave it blank (or write "
                   "\"I don't know\") and let AI draft one from your league setup.")

        def _gen_strategy():
            try:
                _k = st.secrets.get("ANTHROPIC_API_KEY")
            except Exception:
                _k = None
            if not _k:
                st.session_state["_strategy_msg"] = ("err", "Add ANTHROPIC_API_KEY to secrets first.")
                return
            t = int(st.session_state.get("teams", 12))
            s = int(st.session_state.get("slot", 4))
            sc = st.session_state.get("scoring", "PPR")
            seat = "an early" if s <= t // 3 else ("a late/turn" if s >= 2 * t // 3 else "a middle")
            ctx = f"{t}-team snake draft, {sc} scoring, I pick at slot {s} ({seat} pick)."
            try:
                st.session_state["strategy"] = advisor.suggest_strategy(advisor.get_client(_k), ctx)
                st.session_state["_strategy_msg"] = ("ok", "Drafted a strategy — tweak it however you like.")
            except Exception as e:
                st.session_state["_strategy_msg"] = ("err", f"Couldn't generate: {e}")

        try:
            _has_key = bool(st.secrets.get("ANTHROPIC_API_KEY"))
        except Exception:
            _has_key = False
        st.button("Generate one for me", icon=":material/auto_awesome:",
                  on_click=_gen_strategy, disabled=not _has_key)
        _msg = st.session_state.pop("_strategy_msg", None)
        if _msg:
            (st.success if _msg[0] == "ok" else st.error)(_msg[1])

        st.select_slider("Default risk appetite", RISK_LEVELS, key="risk_level",
                         help="Where the Everything board and advisor start. You can still change it live in chat.")
