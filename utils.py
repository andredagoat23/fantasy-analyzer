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


# --- injury-flag severity (shared by tools/injury_watch.py and the live draft page) ---
# Lives here so the tool and the app can never drift apart on what counts as serious.
# The board has NO health input at all (value_board.py doesn't model it) and projections lag an
# injury by days, so these flags are FACTS the board is missing — not a forecast. Availability is
# near-unpredictable (r=+0.019 between last year's games and this year's), but who is hurt RIGHT
# NOW is simply knowable. See icm/work/r1-prerequisites-findings.md.
INJURY_HARD = {"IR", "PUP", "Out", "Doubtful", "NFI", "Sus", "COV", "DNR"}
# `injury_notes` carries signal the status field flattens: a Questionable after surgery is a real
# recovery timeline; a Questionable with "Soreness" is a camp tweak.
INJURY_SERIOUS_NOTE = ("surgery", "procedure", "tear", "torn", "acl", "achilles", "fracture",
                       "broken")


def injury_serious(note):
    """True when an injury note describes a real procedure rather than a minor knock."""
    n = str(note or "").lower()
    return any(k in n for k in INJURY_SERIOUS_NOTE)


def injury_severity(status, note=None):
    """'hard' (PUP/IR/Out) · 'procedure' (flagged + surgery/tear) · 'soft' (flagged) · '' (none).

    Deliberately does NOT gate anyone out of the board — a player on PUP in preseason often returns
    by week 1-4 and can still be real value at his discounted price. This labels; humans decide.
    """
    s = str(status or "").strip()
    if not s:
        return ""
    if s in INJURY_HARD:
        return "hard"
    return "procedure" if injury_serious(note) else "soft"


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