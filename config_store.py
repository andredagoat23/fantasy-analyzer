"""Per-user pre-draft setup persistence.

Each signed-in user's league config is saved to configs/<user>.json so it
survives restarts and family/friend testers don't overwrite each other
(keyed by login). This is the forward-compatible seed for the paid version.
"""
import json
import os

import streamlit as st

CONFIG_DIR = "configs"
# the config fields the setup page owns; these are also the session_state keys
# the draft page reads (slot / teams / risk_level are shared widget keys).
KEYS = ["league_name", "site", "league_id", "teams", "slot",
        "scoring", "scoring_custom", "scoring_parsed", "strategy", "risk_level"]


def _path(user_key):
    safe = "".join(c if c.isalnum() or c in "-_@." else "_" for c in str(user_key)) or "local"
    return os.path.join(CONFIG_DIR, f"{safe}.json")


def load(user_key):
    try:
        with open(_path(user_key)) as f:
            return json.load(f)
    except Exception:          # no saved config yet
        return {}


def save(user_key):
    """Snapshot the current setup (all KEYS) from session_state to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {k: st.session_state.get(k) for k in KEYS}
    with open(_path(user_key), "w") as f:
        json.dump(data, f, indent=2)


def apply(cfg):
    """Push saved values into session_state so widgets pick them up as defaults."""
    for k in KEYS:
        if cfg.get(k) is not None:
            st.session_state[k] = cfg[k]
