import os
import re

import pandas as pd
import streamlit as st

import advisor
import auth
import bridge
import config_store
from utils import normalize_name

try:
    import espn_sync
    ESPN_OK = True
except Exception:              # espn-api not installed -> live sync simply unavailable
    ESPN_OK = False

POSITIONS = ["QB", "RB", "WR", "TE", "K"]
STARTER_CAP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}
FLEX_OK = {"RB", "WR", "TE"}
ROSTER_SLOTS = [("QB", "QB"), ("RB", "RB"), ("RB", "RB"), ("WR", "WR"), ("WR", "WR"),
                ("TE", "TE"), ("FLEX", "FLEX"), ("D/ST", "D/ST"), ("K", "K")]

RANK_OPTIONS = {"ADP": "adp_rank", "Everything": "rank_composite",
                "Value + experts": "rank_ecr", "Value": "overall_rank"}
# Risk-appetite dial (Everything tab): fades risky players by their bust probability (p_bust,
# which blends injury + boom/bust volatility). aversion 0 = rank purely on talent/value.
RISK_PEN = 80
RISK_LEVELS = ["Full send", "Aggressive", "Balanced", "Cautious", "Safe"]
RISK_AVERSION = {"Full send": 0.0, "Aggressive": 0.25, "Balanced": 0.5, "Cautious": 0.75, "Safe": 1.0}
RISK_DESC = {
    "Full send": "Ignore all risk — rank purely on talent and value (no injury or bust penalty).",
    "Aggressive": "Barely fade risk — lean into upside and boom/bust ceilings.",
    "Balanced": "Modest fade for injury-prone and boom/bust players.",
    "Cautious": "Fade risky players noticeably — favor safer floors.",
    "Safe": "Prioritize durable, high-floor players — fade all injury and boom/bust risk hard.",
}
BASE_COLS = ["full_name", "pos_label", "vona", "vols", "adp_rank", "ecr_rank",
             "value_gap", "market", "risk_tier", "xppg", "regression",
             "floor", "ceiling", "p_startable"]

COLUMN_CONFIG = {
    "Mine":      st.column_config.CheckboxColumn("Mine", width="small", help="My pick"),
    "Drafted":   st.column_config.CheckboxColumn("Drafted", width="small", help="Drafted by anyone"),
    "full_name": st.column_config.TextColumn("Player", width="medium"),
    "pos_label": st.column_config.TextColumn("Pos", width="small"),
    "vona":      st.column_config.NumberColumn("VONA", format="%.0f", width="small",
                                               help="Value Over Next Available — points you'd LOSE by "
                                                    "waiting on this player's position until your next "
                                                    "pick (his VOLS minus the best same-position player "
                                                    "ADP says could still be there). Sort by it to see "
                                                    "where the value cliffs are right now."),
    "vols":      st.column_config.NumberColumn("VOLS", format="%.1f"),
    "adp_rank":  st.column_config.NumberColumn("ADP", format="%.1f",
                                               help="ESPN average draft position (live)."),
    "ecr_rank":  st.column_config.NumberColumn("ECR", format="%.0f"),
    "value_gap": st.column_config.NumberColumn("Gap", format="%d"),
    "market":    st.column_config.TextColumn("Market", width="small"),
    "risk_tier": st.column_config.TextColumn("Risk", width="small"),
    "xppg":      st.column_config.NumberColumn("xPPG", format="%.1f",
                                               help="Expected fantasy PPG from 2024-25 opportunity"),
    "regression": st.column_config.TextColumn("Trend", width="small",
                                              help="Actual vs opportunity scoring (position-relative). "
                                                   "🔴 TD-lucky = regression risk · 🟢 Buy-low = efficient/unlucky"),
    "floor":     st.column_config.NumberColumn("Floor", format="%.0f"),
    "ceiling":   st.column_config.NumberColumn("Ceiling", format="%.0f"),
    "p_startable": st.column_config.ProgressColumn("P(start)", format="percent", min_value=0, max_value=1),
}

RISK_BG = {"Safe": "rgba(46,160,67,.20)", "Boom/Bust": "rgba(210,153,34,.20)",
           "Injury Risk": "rgba(229,83,75,.22)"}


@st.cache_data
def load_board(mtime):   # mtime arg busts the cache when the CSV is regenerated
    board = pd.read_csv("value_board.csv", dtype={"player_id": str})
    board["position"] = board["pos_label"].str.replace(r"\d+$", "", regex=True)
    # DEPTH-CHART ROLE (derived, app-layer): each player's rank at his position WITHIN his own team by
    # projected points — so the advisor sees "BUF WR1" vs "DET WR2 (behind the alpha)". Computed on the
    # FULL board (incl. drafted teammates) so the role is the real one, not "best remaining". Reflects
    # the player's CURRENT team (projections are 2026), unlike tgt%/snap% which are last year's.
    board["team_role"] = ""
    has_team = board["team"].notna() & ~board["team"].astype(str).str.upper().isin(["FA", "NAN", ""])
    for (_, pos), grp in board[has_team].groupby(["team", "position"], sort=False):
        rank = grp["total_points"].rank(ascending=False, method="first").astype(int)
        board.loc[grp.index, "team_role"] = pos + rank.astype(str)
    # NO-TEAM (unsigned / FA): no team => no offense, no vegas total, unreliable role -> not draftable.
    board["no_team"] = ~has_team
    return board


def style_board(df):
    css = pd.DataFrame("", index=df.index, columns=df.columns)
    if "vona" in df:   # tint the biggest VONA cells green so the value cliffs pop as you scan
        v = df["vona"].fillna(0)
        thresh = v.quantile(0.75) if len(v) else 0
        css.loc[v >= max(thresh, 1), "vona"] = "background-color: rgba(46,160,67,.22)"
    if "value_gap" in df:
        css.loc[df["value_gap"] > 0, "value_gap"] = "background-color: rgba(46,160,67,.22)"
        css.loc[df["value_gap"] < 0, "value_gap"] = "background-color: rgba(229,83,75,.22)"
    if "risk_tier" in df:
        for tier, bg in RISK_BG.items():
            css.loc[df["risk_tier"] == tier, "risk_tier"] = f"background-color: {bg}"
    if "market" in df:
        css.loc[df["market"].str.contains("VALUE"), "market"] = "background-color: rgba(226,114,91,.25)"
        css.loc[df["market"].str.contains("REACH"), "market"] = "background-color: rgba(76,143,212,.25)"
    return css


board = load_board(os.path.getmtime("value_board.csv"))

# Auto-play the fanfare once every time the draft page is OPENED (via the "Enter the draft"
# button or the top nav) — never on in-page reruns. The audio player is hidden via CSS in app.py,
# so it just autoplays. Drop your own assets/draft_theme.mp3 to override the built-in jingle.
# Fanfare: autoplays when you open the draft page (player hidden via CSS in app.py). Streamlit
# preserves the element across reruns, so it plays through once and never restarts mid-draft.
# Drop your own assets/draft_theme.mp3 to override the built-in jingle.
_theme = "assets/draft_theme.mp3" if os.path.exists("assets/draft_theme.mp3") else "assets/draft_theme.wav"
st.audio(_theme, autoplay=True)

# core columns shown in compact (phone / split-screen) mode — fits a narrow screen
CORE_COLS = ["full_name", "pos_label", "vona", "vols", "adp_rank", "market"]


@st.cache_resource
def get_advisor_client(api_key):   # cached so we reuse one Anthropic client
    return advisor.get_client(api_key)


@st.cache_resource(show_spinner=False)
def connect_league(league_id, year, espn_s2, swid):   # one ESPN connection, reused for polling
    return espn_sync.connect(league_id, year, espn_s2, swid)


@st.cache_data(show_spinner=False)
def espn_maps(mtime):    # espn_id + name lookups from the board (mtime busts on regen)
    return espn_sync.build_maps(board)


@st.cache_data(show_spinner=False)
def board_name_map(mtime):   # {normalized_name -> full_name} for the browser bridge (no espn dep)
    return {normalize_name(n): n for n in board["full_name"]}


def bump():
    st.session_state.version += 1
    st.rerun()


def request_reset():
    st.session_state.confirm_reset = True


def do_reset():
    st.session_state.drafted = set()
    st.session_state.mine = set()
    st.session_state.mine_dst = None
    st.session_state.confirm_reset = False
    st.session_state.version += 1


def cancel_reset():
    st.session_state.confirm_reset = False


def render_roster(mine_df):
    """Draw the slot-filled roster + projected-points metric into the current container.

    Greedy fill: starters first (up to STARTER_CAP per position), then one FLEX from the
    RB/WR/TE overflow, then everything else to the bench. Shared by the sidebar panel and
    the main-page popover so both read identically.
    """
    filled = {k: [] for k in ["QB", "RB", "WR", "TE", "K", "FLEX", "BN"]}
    for _, p in mine_df.iterrows():
        pos = p["position"]
        if pos in STARTER_CAP and len(filled[pos]) < STARTER_CAP[pos]:
            filled[pos].append(p["full_name"])
        elif pos in FLEX_OK and not filled["FLEX"]:
            filled["FLEX"].append(p["full_name"])
        else:
            filled["BN"].append(p["full_name"])
    pools = {k: list(v) for k, v in filled.items()}
    if st.session_state.get("mine_dst"):          # defenses aren't on the board; tracked separately
        pools["D/ST"] = [st.session_state.mine_dst]
    for label, key in ROSTER_SLOTS:
        pool = pools.get(key, [])
        st.markdown(f"**{label}** &nbsp; {pool.pop(0) if pool else '—'}")
    for name in pools["BN"]:
        st.markdown(f"**BN** &nbsp; {name}")
    st.metric("Projected points", f"{mine_df['total_points'].sum():.0f}")
    if mine_df.empty:
        st.caption("Your picks land here as you draft — check **Mine** on the board.")


def render_reset(key_prefix):
    """Reset button + two-step confirm. key_prefix keeps the button IDs unique so the same
    control can render in both the sidebar and the main-page popover (Streamlit forbids
    duplicate widget IDs). The confirm_reset flag + callbacks are shared, so confirming in
    either place clears the draft.
    """
    st.button("Reset draft", icon=":material/refresh:", on_click=request_reset,
              width="stretch", key=f"reset_{key_prefix}")
    if st.session_state.confirm_reset:
        st.warning("Clear all drafted players?", icon=":material/warning:")
        st.button("Yes, reset", on_click=do_reset, width="stretch", key=f"reset_yes_{key_prefix}")
        st.button("Cancel", on_click=cancel_reset, width="stretch", key=f"reset_no_{key_prefix}")


available = board[~board["full_name"].isin(st.session_state.drafted)]
scarcity = {pos: int(((available["position"] == pos) & (available["vols"] >= 0)).sum())
            for pos in POSITIONS}
mine_df = (board[board["full_name"].isin(st.session_state.mine)]
           .sort_values("total_points", ascending=False))

with st.sidebar:
    st.subheader(":material/inventory_2: Position scarcity")
    with st.container(border=True):
        for pos in POSITIONS:
            left = scarcity[pos]
            thin = " :red-badge[thin]" if left <= 5 else ""
            st.markdown(f"**{pos}** &nbsp; {left} startable{thin}")

    st.subheader(":material/groups: My roster")
    with st.container(border=True):
        render_roster(mine_df)

    render_reset("sidebar")

# Compact top strip — exit + the pre-draft knobs tucked into a popover so they don't compete
# with the board during a live draft.
with st.container(horizontal=True):
    if st.button("Exit draft", icon=":material/arrow_back:"):
        config_store.save(auth.current_user_key())   # keep disk current for the setup reseed
        st.switch_page("app_pages/setup.py")
    with st.popover("Draft settings", icon=":material/settings:"):
        _tm = int(st.session_state.get("teams", 12))
        if int(st.session_state.get("slot", 1)) > _tm:   # keep slot within the league
            st.session_state["slot"] = _tm
        st.number_input("My draft slot", 1, _tm, key="slot")
        st.number_input("Teams in league", 2, 20, key="teams")
    # Roster + Reset on the main page too — the sidebar auto-collapses on a phone, so this keeps
    # both one tap away during a live draft. The "· N" is a glanceable pick count.
    with st.popover(f"My roster · {len(st.session_state.mine)}", icon=":material/groups:"):
        render_roster(mine_df)
        render_reset("main")
    st.toggle("Compact view", key="compact",
              help="Trims the board to core columns for phone / split-screen.")

# scarcity readout — always visible on the main page (the sidebar can be hard to reach mid-draft)
strip = " &nbsp;·&nbsp; ".join(f"**{p}** {scarcity[p]} startable left"
                               + (" :red-badge[thin]" if scarcity[p] <= 5 else "")
                               for p in POSITIONS)
st.markdown(f":material/inventory_2: &nbsp; {strip}")

# ---- Live draft sync ----
# Two possible sources. The browser bridge (a userscript posting picks to a Firebase mailbox)
# takes precedence because it works LIVE on any draft site; the ESPN API path is the fallback
# (it only reflects picks after the draft finalizes, so it's for post-draft / testing).
sync_active = False
bridge_url = bridge.db_url()
try:
    espn_cfg = dict(st.secrets.get("espn", {})) if ESPN_OK else {}
except Exception:
    espn_cfg = {}

if bridge_url:
    st.session_state.setdefault("bridge_teams", [])   # team names discovered from incoming picks
    st.session_state.setdefault("bridge_meta_applied", False) # league shape auto-applied once
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            team_opts = ["—"] + st.session_state.bridge_teams
            st.selectbox("Which team is yours?", team_opts, key="bridge_my_team",
                         help="Auto-fills your roster. Fills in once picks start arriving "
                              "(or your browser script can flag your picks directly).")
        with c2:
            sync_active = st.toggle("Live", value=True, key="live_on",
                                    help="Auto-pull picks from your draft site via the browser bridge.")
        dot = "🟢 live" if sync_active else "⚪ paused"
        n = st.session_state.get("pick_count", 0)
        shape = (f" · seat {st.session_state.get('slot')} of {st.session_state.get('teams')} (auto)"
                 if st.session_state.get("bridge_meta_applied") else "")
        st.caption(f"{dot} · browser bridge · {n} pick{'s' if n != 1 else ''} received{shape}")

    if sync_active:
        by_name = board_name_map(os.path.getmtime("value_board.csv"))

        @st.fragment(run_every=4)
        def poll_bridge():
            try:
                payload = bridge.fetch(bridge_url)
            except Exception:
                return   # transient network hiccup — keep last state, retry next tick
            raw, meta = payload["picks"], payload["meta"]

            # Apply the league shape ESPN gave us — ONCE, so manual tweaks afterward stick. teams/slot
            # go through the same *_pending path the AI advisor uses (app.py applies them before the
            # widgets render); myPicks + the team name are stored for mine-detection below.
            if meta and not st.session_state.bridge_meta_applied:
                pend = False
                if meta.get("teams"):
                    st.session_state["teams_pending"] = int(meta["teams"]); pend = True
                if meta.get("slot"):
                    st.session_state["slot_pending"] = int(meta["slot"]); pend = True
                if meta.get("myTeam"):
                    st.session_state.bridge_detected_team = meta["myTeam"]
                st.session_state.bridge_meta_applied = True
                if pend:
                    st.rerun(scope="app")   # let app.py apply teams/slot, then re-poll

            # Your roster = picks whose fantasy owner is YOUR team (auto-detected from ESPN, or the
            # dropdown). Ground truth from the draft site — never guessed from seat numbers, which is
            # what used to pull other teams' picks onto your roster.
            my_team = st.session_state.get("bridge_my_team")
            my_team = None if my_team in (None, "—") else my_team
            my_team = my_team or st.session_state.get("bridge_detected_team")

            drafted, mine, teams_seen, total = bridge.resolve(raw, by_name, my_team)
            my_dst = bridge.my_dst(raw, my_team)   # defenses aren't on the board — track separately
            teams_changed = teams_seen != st.session_state.get("bridge_teams", [])
            if teams_changed:
                st.session_state.bridge_teams = teams_seen
            if (drafted != st.session_state.drafted or mine != st.session_state.mine
                    or total != st.session_state.get("pick_count") or teams_changed
                    or my_dst != st.session_state.get("mine_dst")):
                st.session_state.drafted, st.session_state.mine = drafted, mine
                st.session_state.mine_dst = my_dst
                st.session_state.pick_count = total
                st.session_state.version += 1
                st.rerun(scope="app")   # refresh the whole board with the new picks
        poll_bridge()

elif espn_cfg.get("league_id"):
    with st.container(border=True):
        try:
            league = connect_league(str(espn_cfg["league_id"]), int(espn_cfg.get("year", 2026)),
                                    espn_cfg.get("espn_s2"), espn_cfg.get("swid"))
            team_opts = espn_sync.teams(league)                     # [(id, name)]
            name_to_id = {name: tid for tid, name in team_opts}
            c1, c2 = st.columns([3, 1])
            with c1:
                chosen = st.selectbox("Which team is yours?", ["—"] + [n for _, n in team_opts],
                                      key="my_team_name")
                st.session_state.my_team_id = name_to_id.get(chosen)
            with c2:
                sync_active = st.toggle("Live", value=True, key="live_on",
                                        help="Auto-track picks from your ESPN draft every few seconds.")
            dot = "🟢 live" if sync_active else "⚪ paused"
            hint = "" if st.session_state.get("my_team_id") else " — pick your team to auto-fill your roster"
            st.caption(f"{dot} · ESPN league {espn_cfg['league_id']} · {len(team_opts)} teams{hint}")
        except Exception as e:
            st.warning(f"Couldn't reach your ESPN draft: {e}", icon=":material/wifi_off:")

    if sync_active:
        by_espn, by_name = espn_maps(os.path.getmtime("value_board.csv"))

        @st.fragment(run_every=5)
        def poll_draft():
            try:
                picks = espn_sync.fetch_picks(league, by_espn, by_name)
            except Exception:
                return   # transient ESPN hiccup — keep last state, retry next tick
            drafted = {p["name"] for p in picks if p["name"]}
            mine = {p["name"] for p in picks
                    if p["name"] and p["team_id"] == st.session_state.get("my_team_id")}
            total = len(picks)   # ALL made picks incl. D/ST (which don't map to our board) — keeps
            #                      the on-the-clock count exact even when a pick isn't on our board
            if (drafted != st.session_state.drafted or mine != st.session_state.mine
                    or total != st.session_state.get("pick_count")):
                st.session_state.drafted, st.session_state.mine = drafted, mine
                st.session_state.pick_count = total
                st.session_state.version += 1
                st.rerun(scope="app")   # refresh the whole board with the new picks
        poll_draft()

# Current pick + your next picks, computed from how many players are marked drafted (slot/teams
# come from the Draft settings popover above) and handed to the advisor as exact facts.
slot, teams = int(st.session_state.slot), int(st.session_state.teams)
# when live-synced, use ESPN's exact total pick count (incl. D/ST etc.); else count board removals
made = st.session_state.get("pick_count", 0) if sync_active else len(st.session_state.drafted)
overall_now = made + 1
# My pick numbers = my seat in a standard snake. Computed live from slot + teams (ESPN auto-sets
# the slot, and the Draft settings popover lets me change it), so it always tracks the current
# seat — no sticky hidden state. Enough rounds to cover a full draft.
my_picks = [((r - 1) * teams + slot) if r % 2 else (r * teams - slot + 1) for r in range(1, 21)]
upcoming = [p for p in my_picks if p >= overall_now]
next_pick = upcoming[0] if upcoming else None
following = upcoming[1] if len(upcoming) > 1 else None
my_turn = next_pick == overall_now
picks_away = (next_pick - overall_now) if next_pick else None
draft_pos = {"slot": slot, "teams": teams, "overall_now": overall_now, "my_turn": my_turn,
             "next_pick": next_pick, "following": following, "picks_away": picks_away}
if my_turn:
    nxt = f" &nbsp;·&nbsp; next at #{following}" if following else ""
    st.markdown(f"### :material/sports_football: YOUR PICK — overall #{overall_now}{nxt}")
elif next_pick:
    st.markdown(f"**On the clock:** #{overall_now} &nbsp;·&nbsp; **you're up at #{next_pick}** "
                f"({picks_away} away, then #{following})")

# VONA — points you'd lose by waiting on a position until your next pick. Computed here on the WHOLE
# available board so the AI advisor and the board's VONA column always agree (see advisor.add_vona).
horizon = following if my_turn else next_pick   # my next real chance to pick
available = advisor.add_vona(available, horizon)

# Manual pick tracking — only when NOT live-synced (during a live draft the poller owns this)
if not sync_active:
    with st.container(border=True):
        dc, mc = st.columns(2)
        with dc:
            just_drafted = st.selectbox("Someone drafted", [""] + sorted(available["full_name"]),
                                        key=f"dbox_{st.session_state.version}",
                                        help="Type a name and pick it — removes them from the board.")
        with mc:
            my_pick = st.selectbox("I drafted (my pick)", [""] + sorted(available["full_name"]),
                                   key=f"mbox_{st.session_state.version}",
                                   help="Type your pick — adds to your roster and removes from the board.")
        if my_pick:
            st.session_state.mine.add(my_pick)
            st.session_state.drafted.add(my_pick)
            bump()
        if just_drafted:
            st.session_state.drafted.add(just_drafted)
            bump()

REC_PROMPT = ("I'm on the clock. Given my roster, the board, and my strategy, who should I "
              "take right now and why? Note who'll likely still be there at my next pick.")


def _setup_note():
    """Feed the pre-draft setup (league, scoring, strategy) to the advisor as context."""
    bits = []
    if st.session_state.get("league_name"):
        bits.append(f"League: {st.session_state['league_name']}")
    if st.session_state.get("site"):
        _site = st.session_state["site"]
        if _site == "Other" and st.session_state.get("site_other"):
            _site = st.session_state["site_other"]
        bits.append(f"Draft site: {_site}")
    if st.session_state.get("scoring"):
        sc = st.session_state["scoring"]
        if sc == "Custom" and st.session_state.get("scoring_parsed"):
            bits.append(f"Scoring (custom, my exact league rules):\n{st.session_state['scoring_parsed']}")
        else:
            bits.append(f"Scoring: {sc}")
    if st.session_state.get("strategy"):
        bits.append(f"My stated strategy: {st.session_state['strategy']}")
    return "MY LEAGUE SETUP — " + "; ".join(bits) if bits else ""


with st.container(border=True):
    st.subheader(":material/smart_toy: AI draft advisor")
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:   # no secrets.toml file at all -> treat as "no key"
        api_key = None
    if not api_key:
        st.caption("Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` (and Streamlit Cloud "
                   "secrets) to enable the advisor.")
    else:
        client = get_advisor_client(api_key)
        history_box = st.container(height=240 if st.session_state.compact else 360)
        with history_box:
            if not st.session_state.chat:
                st.caption("Tell me your draft slot, strategy, and risk appetite to start — "
                           "e.g. \"I'm picking 7th in a 12-team snake, Hero-RB, moderate risk.\"")
            for msg in st.session_state.chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        with st.container(horizontal=True):
            rec = st.button("Recommend my pick", icon=":material/bolt:", type="primary")
            if st.button("Clear chat", icon=":material/delete_sweep:"):
                st.session_state.chat = []
                st.rerun()

        typed = st.chat_input("Talk to the advisor…", submit_mode="disable")
        prompt = REC_PROMPT if rec else typed
        mode = "pick" if rec else "chat"   # button = fast terse pick; typing = conversation

        if prompt:
            st.session_state.chat.append({"role": "user", "content": prompt})
            context = advisor.build_context(available, mine_df, scarcity, draft_pos,
                                            my_dst=st.session_state.get("mine_dst"))
            note = _setup_note()
            full_context = f"{note}\n\n{context}" if note else context
            api_messages = (st.session_state.chat[:-1]
                            + [{"role": "user", "content": f"{full_context}\n\n{prompt}"}])
            with history_box:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    try:
                        reply = st.write_stream(advisor.stream_advice(client, api_messages, mode))
                    except Exception as e:
                        reply = f"⚠️ Advisor error: {e}"
                        st.error(reply)
            # the advisor can set the risk dial + my draft slot/teams from chat via [[tags]]
            rtag = re.search(r"\[\[risk:\s*([^\]]+)\]\]", reply, re.I)
            if rtag:
                lvl = next((L for L in RISK_LEVELS if L.lower() == rtag.group(1).strip().lower()), None)
                if lvl:
                    st.session_state["risk_pending"] = lvl
            stag = re.search(r"\[\[slot:\s*(\d+)\]\]", reply, re.I)
            if stag:
                st.session_state["slot_pending"] = int(stag.group(1))
            ttag = re.search(r"\[\[teams:\s*(\d+)\]\]", reply, re.I)
            if ttag:
                st.session_state["teams_pending"] = int(ttag.group(1))
            reply = re.sub(r"\s*\[\[(?:risk|slot|teams):[^\]]+\]\]\s*", "", reply, flags=re.I).strip()
            st.session_state.chat.append({"role": "assistant", "content": reply})
            if any(k in st.session_state for k in ("risk_pending", "slot_pending", "teams_pending")):
                st.rerun()   # re-render so the dial / slot / board reflect the AI's changes

with st.container(horizontal=True):   # wraps to multiple rows on narrow screens
    picked_pos = st.multiselect("Position", POSITIONS, width=200)
    top_n = st.slider("Show top N", min_value=10, max_value=200, value=100, step=10, width=240)
    search = st.text_input("Search player", width=200)
    steals = st.checkbox("🔥 Steals only")
    reaches = st.checkbox("⚠️ Reaches only")

rank_choice = st.segmented_control("Rank by", list(RANK_OPTIONS), default="ADP")
rank_col = RANK_OPTIONS.get(rank_choice, "adp_rank")

# Everything tab: a risk-appetite dial that fades risky (injury-prone / boom-bust) players.
# The AI sets this when you tell it your risk in chat.
if rank_choice == "Everything":
    risk_level = st.select_slider("Risk appetite", RISK_LEVELS, key="risk_level",
                                  help="How hard to fade risky players (injury-prone or boom/bust) on the "
                                       "Everything board. Tell the AI your risk in chat and it moves this for you.")
    st.caption(f":material/tune: **{risk_level}** — {RISK_DESC[risk_level]}")
    av = RISK_AVERSION[risk_level]
    adj = available["rank_composite"] + av * RISK_PEN * available["p_bust"].fillna(0)
    available = available.assign(everything_adj=adj.rank(method="min").astype(int))
    rank_col = "everything_adj"

view = available
if picked_pos:
    view = view[view["position"].isin(picked_pos)]
if search:
    view = view[view["full_name"].str.contains(search, case=False, na=False)]
if steals or reaches:
    allowed = (["VALUE"] if steals else []) + (["REACH"] if reaches else [])
    view = view[view["market"].isin(allowed)]
view = view.sort_values(rank_col).head(top_n)

st.caption(f"{len(view)} available · {len(st.session_state.drafted)} drafted "
           f"({len(st.session_state.mine)} mine) · {len(board)} total")

base_cols = CORE_COLS if st.session_state.compact else BASE_COLS
# dedupe: rank_col may already be in base_cols (e.g. adp_rank) — show it once, first
display_cols = [rank_col] + [c for c in base_cols if c != rank_col]
editor_df = view[display_cols].copy()
editor_df["market"] = editor_df["market"].map({"VALUE": "🔥 VALUE", "REACH": "⚠️ REACH"}).fillna("")
if "regression" in editor_df:
    editor_df["regression"] = editor_df["regression"].map(
        {"TD-lucky": "🔴 TD-lucky", "Buy-low": "🟢 Buy-low"}).fillna("")
editor_df.insert(0, "Drafted", False)
editor_df.insert(0, "Mine", False)

# The sorted column shows as a whole-number "Rank" — EXCEPT ADP, which keeps its decimal
# "ADP" config so you see ESPN's actual number (e.g. 6.3) when sorting by it.
cc = dict(COLUMN_CONFIG)
if rank_col != "adp_rank":
    cc[rank_col] = st.column_config.NumberColumn("Rank", format="%d", width="small")
edited = st.data_editor(
    editor_df.style.apply(style_board, axis=None),
    column_config=cc,
    disabled=display_cols,
    hide_index=True,
    height=460 if st.session_state.compact else 700,
    key=f"board_{st.session_state.version}",
)

newly_mine = edited.loc[edited["Mine"], "full_name"].tolist()
newly_drafted = edited.loc[edited["Drafted"], "full_name"].tolist()
if newly_mine or newly_drafted:
    st.session_state.mine.update(newly_mine)
    st.session_state.drafted.update(newly_mine)
    st.session_state.drafted.update(newly_drafted)
    bump()

with st.expander(f"Drafted ({len(st.session_state.drafted)}) — uncheck to undo", icon=":material/undo:"):
    if st.session_state.drafted:
        undo_df = pd.DataFrame({"Drafted": True, "Player": sorted(st.session_state.drafted)})
        undo_edited = st.data_editor(
            undo_df,
            column_config={"Drafted": st.column_config.CheckboxColumn("Drafted", width="small"),
                           "Player": st.column_config.TextColumn("Player", width="large")},
            disabled=["Player"],
            hide_index=True,
            key=f"undo_{st.session_state.version}",
        )
        restored = undo_edited.loc[~undo_edited["Drafted"], "Player"].tolist()
        if restored:
            st.session_state.drafted.difference_update(restored)
            st.session_state.mine.difference_update(restored)
            bump()
    else:
        st.caption("No players drafted yet.")
