"""JSON store of relevant tenders, keyed by source:id. Keeps first_seen for 'new' detection."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Tender


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.items: dict[str, dict] = {}
        if path.exists():
            self.items = json.loads(path.read_text(encoding="utf-8"))

    def upsert(self, t: Tender, today: date) -> bool:
        """Insert or update. Returns True if the tender is new."""
        d = t.to_dict()
        old = self.items.get(t.key)
        if old:
            d["first_seen"] = old.get("first_seen", today.isoformat())
            # keep winners learned from a later award notice
            d["winners"] = sorted(set(old.get("winners", [])) | set(d["winners"]))
            self.items[t.key] = d
            return False
        d["first_seen"] = today.isoformat()
        self.items[t.key] = d
        return True

    def rescore(self, score_fn, min_score: float) -> int:
        """Re-apply scoring to stored items; drop those now below min_score."""
        drop = []
        for key, d in self.items.items():
            t = Tender.from_dict(d)
            t = score_fn(t)
            if t.score < min_score:
                drop.append(key)
            else:
                d["score"], d["matched"] = t.score, t.matched
        for key in drop:
            del self.items[key]
        return len(drop)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = dict(sorted(self.items.items(), key=lambda kv: (-kv[1]["score"], kv[0])))
        self.path.write_text(json.dumps(ordered, ensure_ascii=False, indent=1), encoding="utf-8")
