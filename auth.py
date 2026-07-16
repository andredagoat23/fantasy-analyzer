"""Login gate.

Auto-detects what's configured in secrets:
  * [auth] block present   -> "Continue with Google" (st.login / OIDC).
  * app_password set        -> polished password gate.
  * neither                 -> open (local dev convenience).

Google, when wired up, takes precedence over the password automatically —
so the app ships working on the password and upgrades itself with no code change.
"""
import streamlit as st


def _has_auth():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def _password():
    try:
        return st.secrets.get("app_password")
    except Exception:
        return None


def is_gated():
    """True when some real login is configured (so we show an account menu)."""
    return _has_auth() or bool(_password())


def _allowed_emails():
    """Optional allow-list of authorized emails (Google sign-in). Empty = any signed-in user."""
    try:
        raw = st.secrets.get("allowed_emails", [])
    except Exception:
        raw = []
    if isinstance(raw, str):
        raw = [raw]
    return [str(e).strip().lower() for e in raw if str(e).strip()]


def _email_ok():
    """True if there's no allow-list, or the signed-in email is on it."""
    allow = _allowed_emails()
    if not allow:
        return True
    try:
        email = (st.user.email or "").strip().lower()
    except Exception:
        email = ""
    return email in allow


def current_user_key():
    """Stable key for per-user config storage."""
    try:
        if getattr(st.user, "is_logged_in", False):
            return st.user.email or "google-user"
    except Exception:
        pass
    return "local"


def user_label():
    try:
        if getattr(st.user, "is_logged_in", False):
            return st.user.email or getattr(st.user, "name", None) or "Signed in"
    except Exception:
        pass
    if st.session_state.get("_authed"):
        return "Signed in"
    return None


def logout():
    if _has_auth():
        st.logout()
    else:
        st.session_state["_authed"] = False


def require_login():
    """Return if authenticated; otherwise render the login screen and stop the run."""
    if _has_auth():
        try:
            if st.user.is_logged_in:
                if _email_ok():
                    return
                _denied_screen()      # signed in, but the email isn't on the allow-list
                st.stop()
        except Exception:
            pass
    else:
        if st.session_state.get("_authed"):
            return
        if not _password():            # nothing configured -> open for local dev
            st.session_state["_authed"] = True
            return

    _login_screen()
    st.stop()


def _hero():
    # Full-screen "front door": hide Streamlit chrome + the sidebar, center a narrow column,
    # and lay a branded hero above the card.
    st.markdown("""
    <style>
      [data-testid="stHeader"], [data-testid="stToolbar"],
      [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      section[data-testid="stSidebar"] { display: none !important; }
      [data-testid="stMainBlockContainer"], .block-container {
        max-width: 600px !important; padding-top: 7vh !important;
      }
      .fa-hero { text-align: center; margin-bottom: 1.1rem; }
      .fa-badge { font-size: 3rem; line-height: 1; }
      .fa-title { font-size: 2.5rem; font-weight: 700; letter-spacing: -.03em; margin: .35rem 0 .1rem;
                  background: linear-gradient(92deg,#E2725B 0%,#E9967A 55%,#F0B49F 100%);
                  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
      .fa-tag { color: #9aa4b2; font-size: 1.05rem; margin: .2rem 0 1.15rem; }
      .fa-chips { display: flex; gap: .45rem; justify-content: center; flex-wrap: wrap; }
      .fa-chip { background: #191E26; border: 1px solid #2A313C; border-radius: 999px;
                 padding: .3rem .85rem; font-size: .82rem; color: #c9d1d9; white-space: nowrap; }
      .fa-foot { text-align: center; color: #6b7280; font-size: .78rem; margin-top: .9rem; }
    </style>
    <div class="fa-hero">
      <div class="fa-badge">🏈</div>
      <div class="fa-title">Fantasy Analyzer</div>
      <div class="fa-tag">Your AI-powered draft war room.</div>
      <div class="fa-chips">
        <span class="fa-chip">🔥 Live value board</span>
        <span class="fa-chip">📊 Vegas-blended projections</span>
        <span class="fa-chip">🤖 AI advisor on the clock</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _foot():
    st.markdown('<div class="fa-foot">Built for draft day · your board, your advisor, one screen.</div>',
                unsafe_allow_html=True)


def _login_screen():
    _hero()
    with st.container(border=True):
        if _has_auth():
            st.markdown("#### Welcome back")
            st.caption("Sign in to open your draft war room.")
            st.button("Continue with Google", type="primary",
                      icon=":material/login:", on_click=st.login, width="stretch")
        else:
            st.markdown("#### Enter your password")
            with st.form("login", border=False):
                pw = st.text_input("Password", type="password",
                                   placeholder="Password", label_visibility="collapsed")
                ok = st.form_submit_button("Sign in", type="primary",
                                           icon=":material/login:", width="stretch")
            if ok:
                if pw and pw == _password():
                    st.session_state["_authed"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.", icon=":material/lock:")
    _foot()


def _denied_screen():
    # signed in with Google, but the email isn't on the allow-list
    _hero()
    try:
        who = st.user.email or "This account"
    except Exception:
        who = "This account"
    with st.container(border=True):
        st.markdown("#### You're not on the guest list yet")
        st.caption(f"**{who}** isn't authorized for this app. Ask the owner to add your email, "
                   "then sign in again.")
        st.button("Sign out", type="primary", icon=":material/logout:",
                  on_click=st.logout, width="stretch")
    _foot()
