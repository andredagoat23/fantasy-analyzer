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