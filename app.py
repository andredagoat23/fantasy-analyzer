import streamlit as st
import pandas as pd
import os

import advisor

st.set_page_config(
    page_title="Fantasy Analyzer",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="auto",   # collapses itself on phone / split-screen widths
)

# tighten padding + shrink the title on narrow viewports (phone / split-screen);
# smaller advisor chat font so more advice fits in the box
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
</style>
""", unsafe_allow_html=True)

POSITIONS = ["QB", "RB", "WR", "TE", "K"]
STARTER_CAP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}
FLEX_OK = {"RB", "WR", "TE"}
ROSTER_SLOTS = [("QB", "QB"), ("RB", "RB"), ("RB", "RB"), ("WR", "WR"), ("WR", "WR"),
                ("TE", "TE"), ("FLEX", "FLEX"), ("D/ST", "D/ST"), ("K", "K")]

RANK_OPTIONS = {"ADP": "adp_rank", "Everything": "rank_composite",
                "Value + experts": "rank_ecr", "Value": "overall_rank"}
BASE_COLS = ["full_name", "pos_label", "vols", "adp_rank", "ecr_rank",
             "value_gap", "market", "risk_tier", "floor", "ceiling", "p_startable"]

COLUMN_CONFIG = {
    "Mine":      st.column_config.CheckboxColumn("Mine", width="small", help="My pick"),
    "Drafted":   st.column_config.CheckboxColumn("Drafted", width="small", help="Drafted by anyone"),
    "full_name": st.column_config.TextColumn("Player", width="medium"),
    "pos_label": st.column_config.TextColumn("Pos", width="small"),
    "vols":      st.column_config.NumberColumn("VOLS", format="%.1f"),
    "adp_rank":  st.column_config.NumberColumn("ADP", format="%.0f"),
    "ecr_rank":  st.column_config.NumberColumn("ECR", format="%.0f"),
    "value_gap": st.column_config.NumberColumn("Gap", format="%d"),
    "market":    st.column_config.TextColumn("Market", width="small"),
    "risk_tier": st.column_config.TextColumn("Risk", width="small"),
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
    return board


def style_board(df):
    css = pd.DataFrame("", index=df.index, columns=df.columns)
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

st.session_state.setdefault("drafted", set())
st.session_state.setdefault("mine", set())
st.session_state.setdefault("version", 0)
st.session_state.setdefault("confirm_reset", False)
st.session_state.setdefault("chat", [])
st.session_state.setdefault("compact", False)

# core columns shown in compact (phone / split-screen) mode — fits a narrow screen
CORE_COLS = ["full_name", "pos_label", "vols", "adp_rank", "market"]


@st.cache_resource
def get_advisor_client(api_key):   # cached so we reuse one Anthropic client
    return advisor.get_client(api_key)


def bump():
    st.session_state.version += 1
    st.rerun()


def request_reset():
    st.session_state.confirm_reset = True


def do_reset():
    st.session_state.drafted = set()
    st.session_state.mine = set()
    st.session_state.confirm_reset = False
    st.session_state.version += 1


def cancel_reset():
    st.session_state.confirm_reset = False


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
        for label, key in ROSTER_SLOTS:
            pool = pools.get(key, [])
            st.markdown(f"**{label}** &nbsp; {pool.pop(0) if pool else '—'}")
        for name in pools["BN"]:
            st.markdown(f"**BN** &nbsp; {name}")
        st.metric("Projected points", f"{mine_df['total_points'].sum():.0f}")

    st.button("Reset draft", icon=":material/refresh:", on_click=request_reset, width="stretch")
    if st.session_state.confirm_reset:
        st.warning("Clear all drafted players?", icon=":material/warning:")
        st.button("Yes, reset", on_click=do_reset, width="stretch")
        st.button("Cancel", on_click=cancel_reset, width="stretch")

st.title("🏈 Fantasy Analyzer — Draft Board")

st.toggle("Compact view", key="compact",
          help="Trims the board to core columns and tightens the layout for phone / split-screen.")

# scarcity strip — always visible, so it stays glanceable when the sidebar is collapsed
strip = "  ·  ".join(f"**{p}** {scarcity[p]}" + (" :red-badge[thin]" if scarcity[p] <= 5 else "")
                     for p in POSITIONS)
st.markdown(f":material/inventory_2: &nbsp; {strip}")

REC_PROMPT = ("I'm on the clock. Given my roster, the board, and my strategy, who should I "
              "take right now and why? Note who'll likely still be there at my next pick.")

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

        typed = st.chat_input("Ask the advisor…", submit_mode="disable")
        prompt = REC_PROMPT if rec else typed

        if prompt:
            st.session_state.chat.append({"role": "user", "content": prompt})
            context = advisor.build_context(available, mine_df, scarcity)
            api_messages = (st.session_state.chat[:-1]
                            + [{"role": "user", "content": f"{context}\n\n{prompt}"}])
            with history_box:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    try:
                        reply = st.write_stream(advisor.stream_advice(client, api_messages))
                    except Exception as e:
                        reply = f"⚠️ Advisor error: {e}"
                        st.error(reply)
            st.session_state.chat.append({"role": "assistant", "content": reply})

with st.container(horizontal=True):   # wraps to multiple rows on narrow screens
    picked_pos = st.multiselect("Position", POSITIONS, width=200)
    top_n = st.slider("Show top N", min_value=10, max_value=200, value=100, step=10, width=240)
    search = st.text_input("Search player", width=200)
    steals = st.checkbox("🔥 Steals only")
    reaches = st.checkbox("⚠️ Reaches only")

rank_choice = st.segmented_control("Rank by", list(RANK_OPTIONS), default="ADP")
rank_col = RANK_OPTIONS.get(rank_choice, "adp_rank")

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
editor_df.insert(0, "Drafted", False)
editor_df.insert(0, "Mine", False)

cc = {**COLUMN_CONFIG, rank_col: st.column_config.NumberColumn("Rank", format="%d", width="small")}
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
