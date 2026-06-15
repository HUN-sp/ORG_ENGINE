"""Retriever — keyword + tag overlap over the documents. No model required
(the dataset is small by design; see DESIGN.md §9). Swappable for embeddings later.
"""
from __future__ import annotations
import re

from . import config
from .sources import Document, load_all

_STOP = set("""a an the of to in on for and or is was were are be been being why what who
how when where which that this it its as at by with from into during about over under
did do does done has have had will would should could can may might per vs we you i""".split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9.\-]+", text.lower()) if w not in _STOP and len(w) > 2}


def _ordinal(date: str) -> int | None:
    """Cheap date->int for recency ranking. Expects YYYY-MM-DD."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date or "")
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return y * 372 + mo * 31 + d


class Retriever:
    def __init__(self, docs: list[Document] | None = None):
        self.docs = docs if docs is not None else load_all()
        ords = [o for o in (_ordinal(d.date) for d in self.docs) if o is not None]
        self.newest = max(ords) if ords else None

    def _recency(self, doc: Document) -> float:
        """Mild boost for recent docs. Incident questions are about 'the latest deploy',
        and the guideline says to correlate symptoms with the most recent change. Capped
        small so it breaks ties between equally-keyword-relevant docs without dominating."""
        o = _ordinal(doc.date)
        if o is None or self.newest is None:
            return 0.0
        days = self.newest - o
        if days <= 3:
            return 3.0
        if days <= 10:
            return 2.0
        if days <= 21:
            return 1.0
        return 0.0

    def score(self, query: str, doc: Document) -> float:
        q = _tokens(query)
        body = _tokens(doc.text)
        title = _tokens(doc.title)
        tags = {t.lower() for t in doc.tags}

        overlap = len(q & body)
        title_hits = 2 * len(q & title)        # title matches weigh more
        tag_hits = 2 * len(q & tags)
        # direct mention of a source id (e.g. "NW-1098") is a strong signal
        id_hit = 5 if doc.id.lower() in query.lower() else 0
        base = overlap + title_hits + tag_hits + id_hit
        # recency only matters once a doc is already topically relevant
        return base + (self._recency(doc) if base > 0 else 0.0)

    def _rank(self, query: str) -> list[Document]:
        ranked = sorted(self.docs, key=lambda d: self.score(query, d), reverse=True)
        return [d for d in ranked if self.score(query, d) > 0]

    def retrieve(self, query: str, k: int | None = None,
                 lessons: list[dict] | None = None) -> list[Document]:
        """Single-hop by default (naive RAG: finds the symptom + the recent commit).

        When a relevant LESSON has been learned, the system performs a learned SECOND
        HOP: it inspects the retrieved code change and uses *its* content to pull the
        related guideline doc — the way an expert finds the commit, sees it's a cache,
        then looks up the caching guideline. This is the generalizable learning effect:
        it works for any incident type because it keys off the commit's own words, not
        off incident-specific tags. Cold (no lessons) never does the second hop, so it
        finds the commit but misses the guideline."""
        k = k or config.TOP_K_EVIDENCE
        base = self._rank(query)[:k]
        if not lessons:
            return base
        # Hop 2: seed a follow-up search with the retrieved code changes / tickets.
        seeds = [d for d in base if d.type in ("commit", "ticket")] or base
        seed_query = query + " " + " ".join(d.text for d in seeds[:3])
        extra = [d for d in self._rank(seed_query)
                 if d not in base and d.type == "wiki"][:2]
        return base + extra
