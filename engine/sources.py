"""Loads the four synthetic knowledge sources into one flat list of Documents.

Each Document has a stable `id` (its source_id) so evidence coverage can be
scored deterministically against the ground-truth gold_evidence ids.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config


@dataclass
class Document:
    id: str
    type: str            # wiki | ticket | slack | commit
    title: str
    text: str            # full searchable text
    tags: list = field(default_factory=list)
    date: str = ""

    def snippet(self, n: int = 600) -> str:
        return self.text if len(self.text) <= n else self.text[:n] + " …"


_WIKI_HEADER = re.compile(
    r"source_id:\s*(?P<id>[\w-]+).*?type:\s*(?P<type>\w+).*?title:\s*(?P<title>[^|>-][^|>]*)",
    re.DOTALL,
)


def _load_wiki() -> list[Document]:
    docs = []
    for path in sorted((config.SOURCES / "wiki").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = _WIKI_HEADER.search(raw)
        sid = m.group("id").strip() if m else path.stem
        title = m.group("title").strip().rstrip("-").strip() if m else path.stem
        body = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()
        tags = re.findall(r"[a-z]{4,}", path.stem.lower())
        docs.append(Document(sid, "wiki", title, body, tags, ""))
    return docs


def _load_tickets() -> list[Document]:
    data = json.loads((config.SOURCES / "tickets" / "issues.json").read_text(encoding="utf-8"))
    docs = []
    for t in data["tickets"]:
        parts = [t["title"], t.get("description", ""), t.get("root_cause", "")]
        for c in t.get("comments", []):
            parts.append(f'{c["author"]}: {c["text"]}')
        for ai in t.get("action_items", []):
            parts.append(f"Action: {ai}")
        if t.get("blocked_by"):
            parts.append("Blocked by: " + ", ".join(t["blocked_by"]))
        if t.get("linked_commits"):
            parts.append("Commits: " + ", ".join(t["linked_commits"]))
        text = f'[{t["type"]} | {t["status"]} | owner {t.get("owner","?")}] ' + "\n".join(p for p in parts if p)
        docs.append(Document(t["id"], "ticket", t["title"], text,
                             t.get("labels", []), t.get("created", "")))
    return docs


def _load_slack() -> list[Document]:
    data = json.loads((config.SOURCES / "slack" / "threads.json").read_text(encoding="utf-8"))
    docs = []
    for th in data["threads"]:
        msgs = "\n".join(f'{m["user"]}: {m["text"]}' for m in th["messages"])
        text = f'{th["channel"]} ({th["kind"]}, {th["date"]})\n{msgs}'
        tags = [th["channel"].strip("#"), th["kind"]]
        docs.append(Document(th["id"], "slack", th["channel"], text, tags, th["date"]))
    return docs


def _load_commits() -> list[Document]:
    data = json.loads((config.SOURCES / "repo" / "commits.json").read_text(encoding="utf-8"))
    docs = []
    for c in data["commits"]:
        text = (f'commit {c["hash"]} by {c["author"]} ({c["date"]}) on {c["service"]} '
                f'[{c.get("ticket","")}]\n{c["message"]}\n{c["diff_summary"]}\n'
                f'released_in: {c.get("released_in","")}')
        tags = [c["service"], c.get("ticket", "")]
        docs.append(Document(c["hash"], "commit", c["message"], text, tags, c["date"]))
    return docs


def load_all() -> list[Document]:
    return _load_wiki() + _load_tickets() + _load_slack() + _load_commits()


if __name__ == "__main__":  # quick sanity check: python -m engine.sources
    for d in load_all():
        print(f'{d.id:18} {d.type:8} {d.title[:50]}')
