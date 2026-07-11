import re

# nickname / alternate-name aliases: map the ODD form -> the canonical (Sleeper) form.
# Applied at the END of normalize_name so both sides of a join converge on the same string.
NAME_ALIASES = {
    "kenny gainwell": "kenneth gainwell",
    "hollywood brown": "marquise brown",
}


def normalize_name(name):
    """Lowercase, strip punctuation and Jr/Sr/III suffixes so names match across sources."""
    s = str(name).lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)            # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()           # squeeze spaces FIRST
    s = re.sub(r" (jr|sr|ii|iii|iv|v)$", "", s)  # then strip a trailing suffix
    return NAME_ALIASES.get(s, s)                # finally, canonicalize known nicknames


# --- startable-tier sizing (12-team league, flex-aware) ---
# Each team locks 2 RB / 2 WR / 1 TE / 1 QB / 1 K, then the 12 FLEX slots go to the
# best remaining RB/WR/TE by projected points. So the RB-vs-WR startable split floats
# with the projections (could be 12 RBs, 12 WRs, or any mix) instead of being fixed.
LOCKED_STARTERS = {"RB": 24, "WR": 24, "TE": 12}   # flex-eligible position minimums (2/2/1 x 12)
FIXED_STARTERS = {"QB": 12, "K": 12}               # no flex slot
N_FLEX = 12
FLEX_POS = tuple(LOCKED_STARTERS)                  # RB, WR, TE


def startable_counts(df, points="total_points", position="position"):
    """How many players are startable at each position, allocating the 12 FLEX slots
    to the highest-projected remaining RB/WR/TE. Returns e.g.
    {"QB": 12, "RB": 31, "WR": 29, "TE": 12, "K": 12}."""
    counts = dict(FIXED_STARTERS)
    locked = set()
    for pos, n in LOCKED_STARTERS.items():
        locked |= set(df[df[position] == pos].nlargest(n, points).index)
    rest = df[df[position].isin(FLEX_POS) & ~df.index.isin(locked)]
    flex_wins = rest.nlargest(N_FLEX, points)[position].value_counts().to_dict()
    for pos, n in LOCKED_STARTERS.items():
        counts[pos] = n + int(flex_wins.get(pos, 0))
    return counts