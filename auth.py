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
                return
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


def _login_screen():
    st.markdown("<div style='height:7vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        with st.container(border=True):
            st.markdown("## 🏈 Fantasy Analyzer")
            st.caption("Your AI-powered draft war room — sign in to continue.")
            st.divider()
            if _has_auth():
                st.button("Continue with Google", type="primary",
                          icon=":material/login:", on_click=st.login, width="stretch")
                st.caption("Secure sign-in via Google.")
            else:
                with st.form("login", border=False):
                    pw = st.text_input("Password", type="password",
                                       placeholder="Enter your password")
                    ok = st.form_submit_button("Sign in", type="primary",
                                               icon=":material/login:", width="stretch")
                if ok:
                    if pw and pw == _password():
                        st.session_state["_authed"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.", icon=":material/lock:")
