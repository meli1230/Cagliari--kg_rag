import re
import unicodedata


def clean_text(text):
    # newlines and extra spaces
    return re.sub(r"\s+", " ", text or "").strip()


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def author_key(last, first):
    # last name + initials, e.g. "berger_el"
    # so "E. L. Berger" and "Edward L. Berger"  ==  same person
    last_n = re.sub(r"[^a-z]", "", strip_accents(last).lower())
    initials = "".join(w[0] for w in strip_accents(first).lower().split() if w[0].isalpha())
    return f"{last_n}_{initials}" if initials else last_n
