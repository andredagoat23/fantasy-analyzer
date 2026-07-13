import streamlit as st

import auth
import config_store

st.set_page_config(
    page_title="Fantasy Analyzer",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="auto",   # collapses itself on phone / split-screen widths
)

# Shared polish, applied to every page:
#  - tighten padding + shrink the title on narrow viewports (phone / split-screen)
#  - smaller advisor chat font so more advice fits in the box
#  - a touch more air around the top navigation
st.markdown("""
<style>
@media (max-width: 820px) {
  [data-testid="stMainBlockContainer"], .block-container {
    padding: 0.7rem 0.8rem 3rem !important;
  }
  h1 { font-size: 1.4rem !important; }
}
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li {
  font-size: 0.84rem;
  line-height: 1.4;
}
[data-testid="stHeader"] { background: transparent; }
/* hide Streamlit's own chrome so it reads as a real app (keep the sidebar toggle) */
[data-testid="stToolbar"], [data-testid="stStatusWidget"] { display: none !important; }
footer { display: none !important; }
/* draft-entry fanfare: autoplay only, no visible player */
[data-testid="stAudio"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ---- login gate (stops the run here if not signed in) ----
auth.require_login()

# ---- shared session state (runs before any page reads it) ----
st.session_state.setdefault("drafted", set())
st.session_state.setdefault("mine", set())
st.session_state.setdefault("version", 0)
st.session_state.setdefault("confirm_reset", False)
st.session_state.setdefault("chat", [])
st.session_state.setdefault("compact", False)
st.session_state.setdefault("risk_level", "Balanced")   # AI / setup can set this
st.session_state.setdefault("slot", 4)                  # my seat in the snake order
st.session_state.setdefault("teams", 12)
st.session_state.setdefault("my_team_id", None)         # my ESPN team (for auto-roster)
# setup-page fields (live widgets keyed to these; loaded from saved config just below)
st.session_state.setdefault("league_name", "")
st.session_state.setdefault("site", "ESPN")
st.session_state.setdefault("site_other", "")
st.session_state.setdefault("league_id", "")
st.session_state.setdefault("scoring", "PPR")
st.session_state.setdefault("scoring_custom", "")
st.session_state.setdefault("strategy", "")
st.session_state.setdefault("active_section", "League")   # which setup card is open

# ---- navigation ----
pages = [
    st.Page("app_pages/setup.py", title="Setup", icon=":material/tune:", default=True),
    st.Page("app_pages/draft.py", title="Draft board", icon=":material/sports_football:"),
]
page = st.navigation(pages, position="hidden")   # move only via Enter draft / Exit draft buttons

# Reseed the saved setup from disk on first load AND on every page switch. Widget-keyed state
# doesn't survive an st.navigation page change, so we reload the (just-saved) values for the page
# we're entering. Within a page there's no switch, so live edits are untouched.
if st.session_state.get("_nav_at") != page.title:
    st.session_state["_nav_at"] = page.title
    config_store.apply(config_store.load(auth.current_user_key()))

# apply slot/teams/risk the AI set from chat, before those widgets render (after the reseed above)
if "slot_pending" in st.session_state:
    st.session_state["slot"] = max(1, min(20, st.session_state.pop("slot_pending")))
    st.toast(f"Draft slot set to #{st.session_state['slot']}", icon=":material/sports_football:")
if "teams_pending" in st.session_state:
    st.session_state["teams"] = max(2, min(20, st.session_state.pop("teams_pending")))
if "risk_pending" in st.session_state:
    st.session_state["risk_level"] = st.session_state.pop("risk_pending")
    st.toast(f"Risk appetite set to **{st.session_state['risk_level']}**", icon=":material/tune:")

# Keep config widget values alive across conditional (setup-card) rendering: re-assigning a
# widget key to itself stops Streamlit from clearing it when its widget isn't rendered this run.
for _k in ("league_name", "site", "site_other", "league_id", "teams", "slot",
           "scoring", "scoring_custom", "strategy", "risk_level"):
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

# branded header + account menu, above the page content
hl, hr = st.columns([4, 1], vertical_alignment="center")
with hl:
    st.markdown("### 🏈 Fantasy Analyzer")
with hr:
    if auth.is_gated():
        who = auth.user_label()                              # email (Google) / "Signed in" / None
        short = (who.split("@")[0] if who and "@" in who else who) or "Account"
        with st.popover(short, icon=":material/account_circle:", width="stretch"):
            if who and "@" in who:
                st.caption(f"Signed in as **{who}**")
            st.button("Sign out", icon=":material/logout:", on_click=auth.logout, width="stretch")

page.run()
