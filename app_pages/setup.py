import streamlit as st

import advisor
import auth
import config_store

SITES = ["ESPN", "Sleeper", "Yahoo", "Other"]
SCORING = ["PPR", "Half-PPR", "Standard", "Custom"]
RISK_LEVELS = ["Full send", "Aggressive", "Balanced", "Cautious", "Safe"]

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
st.caption("Set everything up here before draft day, so the board is pure speed once the clock starts.")

# ESPN live-sync status is read from secrets — cookies are never entered in the UI.
try:
    espn_ready = bool(dict(st.secrets.get("espn", {})).get("league_id"))
except Exception:
    espn_ready = False

# Fields are live (not batched in a form) so the slot max follows league size immediately, and
# they're keyed to session_state so values persist across reruns without a submit.
with st.container(border=True):
    st.markdown("**:material/emoji_events: League**")
    st.text_input("League name", key="league_name", placeholder="e.g. The Sunday Scaries")
    st.segmented_control("Drafting site", SITES, key="site")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("League size (teams)", 2, 20, key="teams")
    with c2:
        _tm = int(st.session_state.get("teams", 12))
        if int(st.session_state.get("slot", 1)) > _tm:      # keep slot within the league
            st.session_state["slot"] = _tm
        st.number_input("Your draft slot", 1, _tm, key="slot",
                        help="Your seat in the snake order. Caps at your league size.")

with st.container(border=True):
    st.markdown("**:material/link: Connection**")
    st.text_input("League ID", key="league_id",
                  help="Found in your league URL. For live ESPN sync, also add it to secrets.")
    if espn_ready:
        st.success("ESPN live sync is connected — picks auto-track during your draft.",
                   icon=":material/wifi:")
    else:
        st.info("ESPN live sync isn't configured, so you'll track picks manually on the board. "
                "Add an `[espn]` block to secrets to enable auto-tracking.",
                icon=":material/wifi_off:")

with st.container(border=True):
    st.markdown("**:material/functions: Scoring**")
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

with st.container(border=True):
    st.markdown("**:material/strategy: Strategy defaults**")
    st.text_area("Your draft strategy", key="strategy",
                 placeholder="e.g. Hero RB — lock one elite RB early, then hammer WR. "
                             "Wait on QB until round 8+. Stream D/ST and K late.")
    st.select_slider("Default risk appetite", RISK_LEVELS, key="risk_level",
                     help="Where the Everything board and advisor start. You can still change it live in chat.")
