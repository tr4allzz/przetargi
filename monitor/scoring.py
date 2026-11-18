"""Relevance scoring 0–10 for Valready (CSV / GxP validation)."""
from __future__ import annotations

import re

from . import config
from .models import Tender

_TERMS = [(w, label, re.compile(rx, re.I | re.S)) for w, label, rx in config.TERMS]
_NEG = [(w, label, re.compile(rx, re.I | re.S)) for w, label, rx in config.NEGATIVE]
_STRONG_LABELS = {label for w, label, _ in config.TERMS if w == config.STRONG}


def score(t: Tender) -> Tender:
    text = t.text()
    raw = 0.0
    matched: list[str] = []
    for w, label, rx in _TERMS:
        if rx.search(text):
            raw += w
            matched.append(label)

    has_validation = bool(config.REQUIRE_ANY_LABEL & set(matched))
    has_strong = bool(_STRONG_LABELS & set(matched))
    has_context = bool(config.CONTEXT_LABELS & set(matched))
    if not has_validation or not (has_strong or has_context):
        t.score, t.matched = 0.0, matched
        return t

    for prefix, bonus in config.CPV_BONUS.items():
        if any(c.startswith(prefix) for c in t.cpv):
            raw += bonus
            matched.append(f"CPV {prefix}*")
            break  # take the most specific bonus only (dict is ordered specific→broad)

    for w, label, rx in _NEG:
        if rx.search(text):
            raw -= w
            matched.append(f"-{label}")

    t.score = round(max(0.0, min(10.0, raw)), 1)
    t.matched = matched
    return t
