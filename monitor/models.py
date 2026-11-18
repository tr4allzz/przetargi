"""Normalized tender record shared by all sources."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Tender:
    source: str                 # e.g. "ted", "fts", "ezamowienia"
    source_id: str              # stable id within the source
    title: str
    url: str = ""
    description: str = ""
    buyer: str = ""
    country: str = ""
    published: str = ""         # ISO date (YYYY-MM-DD)
    deadline: str = ""          # ISO date or datetime, if known
    notice_type: str = ""       # tender / award / plan / ...
    cpv: list[str] = field(default_factory=list)
    value: str = ""             # human-readable, e.g. "94080 GBP"
    winners: list[str] = field(default_factory=list)
    # filled by scoring
    score: float = 0.0
    matched: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def text(self) -> str:
        return " ".join([self.title, self.description, self.buyer]).lower()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["key"] = self.key
        return d
