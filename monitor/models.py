"""Normalized tender record shared by all sources."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Tender:
    source: str                 # e.g. "ted", "ezamowienia", "bk"
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
    value: str = ""             # legacy free-text value
    winners: list[str] = field(default_factory=list)
    # --- bid-intelligence fields (filled when the source provides them) ---
    tender_id: str = ""         # procedure id linking notice <-> result (e-Zamówienia ocds id)
    procedure: str = ""         # tryb / procedure type
    estimated_value: str = ""   # wartość szacunkowa, e.g. "200000.00 PLN"
    award_value: str = ""       # wartość umowy / cena wybranej oferty
    lowest_offer: str = ""
    highest_offer: str = ""
    offers: str = ""            # liczba ofert (per lot joined with "/")
    criteria: list[str] = field(default_factory=list)   # e.g. ["Cena 60", "Doświadczenie 40"]
    duration: str = ""          # okres realizacji
    contract_date: str = ""
    framework: str = ""         # umowa ramowa?
    deposit: str = ""           # wadium
    conditions: str = ""        # warunki udziału (skrót)
    winner_info: list[str] = field(default_factory=list)  # e.g. ["DEU, large"]
    # filled by scoring
    kind: str = ""              # usługa CSV / system + walidacja / sprzęt + IQ/OQ / serwis urządzeń / inne
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

    @classmethod
    def from_dict(cls, d: dict) -> "Tender":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
