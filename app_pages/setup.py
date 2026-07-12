import streamlit as st

import advisor
import auth
import config_store

SITES = ["ESPN", "Sleeper", "Yahoo", "Other"]
SCORING = ["PPR", "Half-PPR", "Standard", "Custom"]
RISK_LEVELS = ["Full send", "Aggressive", "Balanced", "Cautious", "Safe"]

st.markdown("#### :material/tune: Pre-draft setup")
st.caption("Set everything up here before draft day, so the board is pure speed once the clock starts.")

# ESPN live-sync status is read from secrets — cookies are never entered in the UI.
try:
    espn_ready = bool(dict(st.secrets.get("espn", {})).get("league_id"))
except Exception:
    espn_ready = False

with st.form("setup"):
    with st.container(border=True):
        st.markdown("**:material/emoji_events: League**")
        league_name = st.text_input("League name", value=st.session_state.get("league_name", ""),
                                     placeholder="e.g. The Sunday Scaries")
        site = st.segmented_control("Drafting site", SITES,
                                    default=st.session_state.get("site", "ESPN"))
        c1, c2 = st.columns(2)
        teams = int(c1.number_input("League size (teams)", 2, 20, st.session_state.get("teams", 12)))
        slot = c2.number_input("Your draft slot", 1, teams,
                               min(int(st.session_state.get("slot", 4)), teams),
                               help="Your seat in the snake order — pick 1 drafts first each odd round. "
                                    "Caps at your league size.")

    with st.container(border=True):
        st.markdown("**:material/link: Connection**")
        league_id = st.text_input("League ID", value=st.session_state.get("league_id", ""),
                                  help="Found in your league URL. For live ESPN sync, also add it to secrets.")
        if espn_ready:
            st.success("ESPN live sync is connected — picks auto-track during your draft.",
                       icon=":material/wifi:")
        else:
            st.info("ESPN live sync isn't configured, so you'll track picks manually on the board. "
                    "Add an `[espn]` block to secrets to enable auto-tracking.",
                    icon=":material/wifi_off:")

    with st.container(border=True):
        st.markdown("**:material/strategy: Strategy defaults**")
        strategy = st.text_area("Your draft strategy", value=st.session_state.get("strategy", ""),
                                placeholder="e.g. Hero RB — lock one elite RB early, then hammer WR. "
                                            "Wait on QB until round 8+. Stream D/ST and K late.")
        risk_level = st.select_slider("Default risk appetite", RISK_LEVELS,
                                      value=st.session_state.get("risk_level", "Balanced"),
                                      help="Where the Everything board and advisor start. "
                                           "You can still change it live in chat.")

    saved = st.form_submit_button("Save setup", type="primary", icon=":material/save:")

if saved:
    cfg = {"league_name": league_name, "site": site, "league_id": league_id,
           "teams": int(teams), "slot": int(slot),          # scoring lives in its own block below
           "strategy": strategy, "risk_level": risk_level}
    config_store.apply(cfg)                        # push into session_state now
    config_store.save(auth.current_user_key())     # persist the full setup for next time
    st.toast("Setup saved — you're ready for draft day.", icon=":material/check_circle:")

# ---- Scoring — its own block (interactive AI decipher can't live inside the save form) ----
with st.container(border=True):
    st.markdown("**:material/functions: Scoring**")
    scoring = st.segmented_control("League scoring", SCORING,
                                   default=st.session_state.get("scoring", "PPR")) or "PPR"
    st.session_state["scoring"] = scoring
    if scoring != st.session_state.get("_scoring_last"):     # persist a preset change immediately
        st.session_state["_scoring_last"] = scoring
        config_store.save(auth.current_user_key())

    if scoring == "Custom":
        st.caption("Paste your league's exact scoring rules and let AI translate them into a clean "
                   "breakdown the advisor will use. (This informs the advisor — the board's rankings "
                   "stay as computed in the pipeline.)")
        raw = st.text_area("Your scoring settings", value=st.session_state.get("scoring_custom", ""),
                           height=150,
                           placeholder="Paste from your league settings, e.g. Passing TD 4, INT -2, "
                                       "Rush/Rec TD 6, Reception 0.5, 100+ rush/rec yds +3 …")
        st.session_state["scoring_custom"] = raw
        try:
            _api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            _api_key = None
        go = st.button("Decipher with AI", icon=":material/auto_awesome:", type="primary",
                       disabled=not (_api_key and raw.strip()))
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

st.divider()
st.caption("Everything set? Lock it in and drop into the draft room.")
if st.button("🏈 Enter the draft", type="primary", width="stretch"):
    st.switch_page("app_pages/draft.py")
