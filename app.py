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

# load this user's saved pre-draft setup once per session (overrides the defaults above)
if not st.session_state.get("_config_loaded"):
    config_store.apply(config_store.load(auth.current_user_key()))
    st.session_state["_config_loaded"] = True

# apply slot/teams the AI set from chat, before those number_inputs render
if "slot_pending" in st.session_state:
    st.session_state["slot"] = max(1, min(16, st.session_state.pop("slot_pending")))
    st.toast(f"Draft slot set to #{st.session_state['slot']}", icon=":material/sports_football:")
if "teams_pending" in st.session_state:
    st.session_state["teams"] = max(2, min(16, st.session_state.pop("teams_pending")))
# apply a risk level the AI requested last turn, before the slider widget is created
if "risk_pending" in st.session_state:
    st.session_state["risk_level"] = st.session_state.pop("risk_pending")
    st.toast(f"Risk appetite set to **{st.session_state['risk_level']}**", icon=":material/tune:")

# ---- navigation ----
pages = [
    st.Page("app_pages/setup.py", title="Setup", icon=":material/tune:", default=True),
    st.Page("app_pages/draft.py", title="Draft board", icon=":material/sports_football:"),
]
page = st.navigation(pages, position="top")

# branded header + account menu, above the page content
hl, hr = st.columns([4, 1], vertical_alignment="center")
with hl:
    st.markdown("### 🏈 Fantasy Analyzer")
with hr:
    if auth.is_gated():
        label = auth.user_label() or "Account"
        with st.popover(label, icon=":material/account_circle:", width="stretch"):
            st.button("Sign out", icon=":material/logout:", on_click=auth.logout, width="stretch")

page.run()
