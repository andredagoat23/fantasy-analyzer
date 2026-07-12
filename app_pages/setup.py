import streamlit as st

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
        teams = c1.number_input("League size (teams)", 2, 16, st.session_state.get("teams", 12))
        slot = c2.number_input("Your draft slot", 1, 16, st.session_state.get("slot", 4),
                               help="Your seat in the snake order — pick 1 drafts first each odd round.")

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
        st.markdown("**:material/functions: Scoring**")
        scoring = st.segmented_control("League scoring", SCORING,
                                       default=st.session_state.get("scoring", "PPR"))
        st.caption("This tells the AI advisor how your league scores. Note: the board's rankings are "
                   "pre-computed for your custom scoring in the data pipeline — this selector informs "
                   "the advisor, it doesn't re-rank the board here.")

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
           "teams": int(teams), "slot": int(slot), "scoring": scoring,
           "strategy": strategy, "risk_level": risk_level}
    config_store.apply(cfg)                          # push into session_state now
    config_store.save(auth.current_user_key(), cfg)  # persist for next time
    st.toast("Setup saved — you're ready for draft day.", icon=":material/check_circle:")

st.caption("When you're set, head to **Draft board** in the top menu.")
