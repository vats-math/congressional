"""Content-based recommender: TF-IDF vectors + cosine similarity (no LLM).

Used two ways:
  * query -> opportunity text relevance (one factor in the ranking)
  * opportunity -> opportunity "similar programs" lookups
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "i", "im", "in", "is",
    "it", "my", "of", "on", "or", "the", "to", "want", "with", "find", "play", "looking",
    "am", "me", "near", "into", "who", "that", "this", "years", "old", "opportunities",
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def document(opp: dict[str, Any]) -> str:
    parts = [
        opp["name"], opp["organization"], opp["type"], opp["sport"], opp["sport"],
        " ".join(opp["skill_levels"]), opp["description"], opp["eligibility"],
        opp["city"], opp["region"], opp["country"], "travel" if opp["is_travel"] else "local",
    ]
    return " ".join(str(p) for p in parts)


class TfidfIndex:
    def __init__(self, rows: list[dict[str, Any]]):
        self.ids = [r["id"] for r in rows]
        docs = [Counter(tokenize(document(r))) for r in rows]
        n = max(len(docs), 1)
        df: Counter[str] = Counter()
        for d in docs:
            df.update(d.keys())
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.vectors = {i: self._weigh(d) for i, d in zip(self.ids, docs)}

    def _weigh(self, counts: Counter[str]) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items() if v}

    @staticmethod
    def _cos(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(t, 0.0) for t, v in a.items())

    def query_scores(self, text: str) -> dict[str, float]:
        q = self._weigh(Counter(tokenize(text)))
        if not q:
            return {}
        return {i: self._cos(q, v) for i, v in self.vectors.items()}

    def similar(self, opp_id: str, k: int = 5) -> list[tuple[str, float]]:
        base = self.vectors.get(opp_id)
        if base is None:
            return []
        scored = [(i, self._cos(base, v)) for i, v in self.vectors.items() if i != opp_id]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
