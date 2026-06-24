import re


def normalize_name(name):
    """Lowercase, strip punctuation and Jr/Sr/III suffixes so names match across sources."""
    s = str(name).lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)            # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()           # squeeze spaces FIRST
    s = re.sub(r" (jr|sr|ii|iii|iv|v)$", "", s)  # then strip a trailing suffix
    return s
