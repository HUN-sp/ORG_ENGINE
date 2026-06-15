"""Long-term memory = the lesson store (Reflexion episodic buffer).

- starts empty (`lessons.json` -> {"lessons": []})
- retrieve(question) returns the top-K most relevant lessons (bounded, like Reflexion's Ω)
- add(lesson) appends and persists
- record_use(id, won) tracks whether a lesson actually helped (quality control)
"""
from __future__ import annotations
import json
import re

from . import config

_STOP = set("a an the of to in on for and or is why what who how when where which that this it".split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9\-]+", text.lower()) if w not in _STOP and len(w) > 2}


# Words that signal a causal / incident "why did X go wrong?" question. A lesson learned
# on one incident type (e.g. a migration) must generalize to another (e.g. an OOM) — the
# reasoning pattern is shared even when the surface vocabulary isn't. Matching on this
# family is what makes generalization actually fire.
_CAUSAL = {"why", "cause", "caused", "root", "fail", "failed", "failure", "broke", "broken",
           "crash", "crashed", "oom", "oomkilled", "latency", "slow", "slowed", "spike",
           "spiked", "delayed", "delay", "error", "errors", "down", "blocked", "stuck",
           "leak", "outage", "incident", "regression", "degraded"}


def _is_causal(text: str) -> bool:
    return bool(_tokens(text) & _CAUSAL)


class Memory:
    def __init__(self, path=None):
        self.path = path or config.LESSONS_FILE
        blob = json.loads(self.path.read_text(encoding="utf-8"))
        self._meta = blob.get("_meta", {})
        self.lessons = blob.get("lessons", [])

    # ---- read ----
    def _relevance(self, question: str, lesson: dict) -> int:
        q = _tokens(question)
        keys = _tokens(lesson.get("trigger_pattern", "")) | {t.lower() for t in lesson.get("tags", [])}
        score = len(q & keys)
        # cross-incident generalization: a causal question matches a causal lesson even
        # when the specific vocabulary differs (migration vs OOM vs latency).
        trigger_text = lesson.get("trigger_pattern", "") + " " + " ".join(lesson.get("tags", []))
        if _is_causal(question) and _is_causal(trigger_text):
            score += 2
        return score

    def retrieve(self, question: str, k: int | None = None) -> list[dict]:
        k = k or config.TOP_K_LESSONS
        ranked = sorted(self.lessons, key=lambda l: self._relevance(question, l), reverse=True)
        return [l for l in ranked if self._relevance(question, l) > 0][:k]

    # ---- write ----
    def next_id(self) -> str:
        return f"LSN-{len(self.lessons) + 1:03d}"

    def add(self, lesson: dict) -> dict:
        lesson.setdefault("id", self.next_id())
        lesson.setdefault("uses", 0)
        lesson.setdefault("wins", 0)
        self.lessons.append(lesson)
        self.save()
        return lesson

    def record_use(self, lesson_ids: list[str], won: bool):
        for l in self.lessons:
            if l["id"] in lesson_ids:
                l["uses"] = l.get("uses", 0) + 1
                if won:
                    l["wins"] = l.get("wins", 0) + 1
        self.save()

    def save(self):
        self.path.write_text(
            json.dumps({"_meta": self._meta, "lessons": self.lessons}, indent=2),
            encoding="utf-8",
        )

    def reset(self):
        """Clear all learned lessons (handy to re-run the demo from scratch)."""
        self.lessons = []
        self.save()
