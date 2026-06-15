"""Shared pipeline: run the full learning cycle for one question and return a
structured result (no printing). Used by both run.py (CLI) and app.py (UI)."""
from __future__ import annotations

from . import actor, evaluator, reflector
from .retriever import Retriever
from .memory import Memory


def _ev(docs):
    return [{"id": d.id, "type": d.type, "title": d.title} for d in docs]


def process_question(question: str, expert: dict, retriever: Retriever, memory: Memory) -> dict:
    """V1 (with whatever lessons exist) -> human answer -> gap -> lesson -> V2."""
    # 1. recall (lesson-aware; lessons from earlier questions help here too)
    lessons_v1 = memory.retrieve(question)
    evidence_v1 = retriever.retrieve(question, lessons=lessons_v1)

    # 2. Version 1
    v1 = actor.answer(question, evidence_v1, lessons_v1)
    s1 = evaluator.score(v1, expert)

    # 3. human-in-the-loop -> gap analysis -> lesson
    gap = reflector.gap_analysis(question, v1, expert)
    lesson = reflector.make_lesson(question, v1, expert, gap)
    lesson = memory.add(lesson)

    # 4. Version 2 (re-run with the new lesson; retrieval is now lesson-aware)
    lessons_v2 = memory.retrieve(question)
    evidence_v2 = retriever.retrieve(question, lessons=lessons_v2)
    v2 = actor.answer(question, evidence_v2, lessons_v2)
    s2 = evaluator.score(v2, expert)

    gain = round(s2["overall"] - s1["overall"], 1)
    memory.record_use([lesson["id"]], won=gain > 0)

    return {
        "question": question,
        "lessons_available_at_v1": [l["id"] for l in lessons_v1],
        "gold_evidence": expert.get("gold_evidence", []),
        "evidence_v1": _ev(evidence_v1),
        "evidence_v2": _ev(evidence_v2),
        "v1": {**v1, "scores": s1},
        "human": {
            "expert": expert.get("expert", ""),
            "answer": expert["answer"],
            "root_cause": expert.get("root_cause", "N/A"),
        },
        "gap": gap,
        "lesson": lesson,
        "v2": {**v2, "scores": s2},
        "gain": gain,
    }
