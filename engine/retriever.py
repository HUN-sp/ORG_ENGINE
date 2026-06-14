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


class Retriever:
    def __init__(self, docs: list[Document] | None = None):
        self.docs = docs if docs is not None else load_all()

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
        return overlap + title_hits + tag_hits + id_hit

    def _expand(self, query: str, lessons: list[dict] | None) -> str:
        """Lesson-aware retrieval: a learned lesson tells us which SOURCE TYPES to
        look for (e.g. 'check the triggering commit and the wiki guideline'), so we
        fold the lesson's vocabulary into the search query. This is what lets V2 (and
        generalized first answers) surface evidence the bare question can't reach."""
        if not lessons:
            return query
        extra = []
        for l in lessons:
            extra += l.get("tags", [])
            extra += [l.get("trigger_pattern", ""), l.get("reasoning_rule", ""),
                      l.get("evidence_rule", "")]
        return query + " " + " ".join(extra)

    def retrieve(self, query: str, k: int | None = None,
                 lessons: list[dict] | None = None) -> list[Document]:
        k = k or config.TOP_K_EVIDENCE
        q = self._expand(query, lessons)
        ranked = sorted(self.docs, key=lambda d: self.score(q, d), reverse=True)
        return [d for d in ranked if self.score(q, d) > 0][:k]
