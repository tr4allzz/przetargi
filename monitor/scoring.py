"""Relevance scoring 0–10 for Valready (CSV / GxP validation)."""
from __future__ import annotations

import re

from . import config
from .models import Tender

_TERMS = [(w, label, re.compile(rx, re.I | re.S)) for w, label, rx in config.TERMS]
_NEG = [(w, label, re.compile(rx, re.I | re.S)) for w, label, rx in config.NEGATIVE]
_STRONG_LABELS = config.SELF_SUFFICIENT_LABELS
_GIG_TITLE = re.compile(config.RX_GIG_TITLE, re.I)


_K = {name: re.compile(getattr(config, name), re.I | re.S) for name in
      ("RX_DEVICE_SERVICE", "RX_DELIVERY", "RX_SYSTEM", "RX_EQUIPMENT", "RX_SERVICE", "RX_OTHER")}


def classify(t: Tender) -> str:
    """Rule-based tender type. Title decides first; description only breaks ties."""
    if t.source == "freelancermap":
        return config.KIND_FREELANCE
    title = (t.title or "").lower()
    full = t.text()
    hit = lambda name, txt: bool(_K[name].search(txt))  # noqa: E731
    equip_cpv = any(c.startswith(config.EQUIPMENT_CPV_PREFIXES) for c in t.cpv)

    if hit("RX_DEVICE_SERVICE", title):
        return config.KIND_DEVICE_SERVICE
    if hit("RX_OTHER", title) and not hit("RX_SYSTEM", title):
        return config.KIND_OTHER
    delivery = hit("RX_DELIVERY", title)
    if hit("RX_SYSTEM", title) and (delivery or not hit("RX_SERVICE", title)):
        # "Walidacja i utrzymanie zainstalowanego systemu" = service on an existing system
        if not delivery and re.match(r"\s*(walidacj|validat|validier)", title):
            return config.KIND_SERVICE
        return config.KIND_SYSTEM
    if delivery and (hit("RX_EQUIPMENT", title) or equip_cpv):
        return config.KIND_EQUIPMENT
    if hit("RX_EQUIPMENT", title) and not hit("RX_SERVICE", title):
        return config.KIND_EQUIPMENT
    if hit("RX_SERVICE", title) or any(c.startswith(("72", "79", "71")) for c in t.cpv):
        if hit("RX_OTHER", full) and not hit("RX_SYSTEM", full):
            return config.KIND_OTHER
        return config.KIND_SERVICE
    # fall back to the description
    if hit("RX_DEVICE_SERVICE", full):
        return config.KIND_DEVICE_SERVICE
    if hit("RX_SYSTEM", full) and hit("RX_DELIVERY", full):
        return config.KIND_SYSTEM
    if equip_cpv or hit("RX_EQUIPMENT", full):
        return config.KIND_EQUIPMENT
    return config.KIND_OTHER


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
        t.score, t.matched, t.kind = 0.0, matched, ""
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

    t.kind = classify(t)
    if "-analytical method validation" in matched:
        t.kind = config.KIND_OTHER   # walidacja metod analitycznych to nie CSV
    raw += config.KIND_SCORE_ADJ.get(t.kind, 0.0)
    if t.kind == config.KIND_FREELANCE and not _GIG_TITLE.search(t.title or ""):
        raw -= config.GIG_TITLE_PENALTY
        matched.append("-gig title off-topic")

    t.score = round(max(0.0, min(10.0, raw)), 1)
    t.matched = matched
    return t
