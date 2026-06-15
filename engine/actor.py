"""Actor (Reflexion M_a) — drafts an answer + reasoning trace + cited evidence +
confidence, conditioned on retrieved evidence AND any injected lessons.

Injecting lessons is the mechanism by which the system 'learns': the model is
unchanged, but its instructions grow richer with each correction.
"""
from __future__ import annotations
from .llm_client import llm_json
from .sources import Document

# NOTE: the base prompt is deliberately NEUTRAL. It does NOT tell the model how to
# investigate (e.g. "trace causes, don't stop at symptoms"). That expert reasoning is
# exactly what the system must LEARN, and it arrives only via injected lessons. Baking
# it in here would make the no-memory baseline already expert-level and erase the
# measurable learning effect.
SYSTEM = (
    "You answer organizational questions using ONLY the evidence provided. "
    "Cite the exact source ids you used. "
    "If the evidence is insufficient to answer confidently, say so and lower your "
    "confidence — never invent certainty."
)


def _format_evidence(docs: list[Document]) -> str:
    return "\n\n".join(f"[{d.id}] ({d.type}) {d.title}\n{d.snippet()}" for d in docs)


def _format_lessons(lessons: list[dict]) -> str:
    if not lessons:
        return "(none yet)"
    out = []
    for l in lessons:
        out.append(
            f"- {l.get('reasoning_rule','')}\n  Evidence rule: {l.get('evidence_rule','')}"
            f"\n  Confidence: {l.get('confidence_adjustment','')}"
        )
    return "\n".join(out)


def answer(question: str, evidence: list[Document], lessons: list[dict]) -> dict:
    prompt = f"""QUESTION:
{question}

LESSONS FROM PAST CORRECTIONS (apply these — they tell you how an expert reasons about this kind of question):
{_format_lessons(lessons)}

EVIDENCE (cite ids exactly as shown, e.g. NW-1098, a3f9c2, WIKI-migrations, SLK-001):
{_format_evidence(evidence)}

Return a JSON object with EXACTLY these fields:
{{
  "answer": "a clear, complete answer a senior engineer would give",
  "root_cause": "the single underlying cause, or 'N/A' if the question is not about a failure",
  "reasoning_trace": ["step 1 ...", "step 2 ...", "..."],
  "evidence_used": ["source ids you actually relied on"],
  "confidence": 0.0
}}"""
    result = llm_json(prompt, system=SYSTEM)
    # normalise
    result.setdefault("root_cause", "N/A")
    result["evidence_used"] = [str(e).strip() for e in result.get("evidence_used", [])]
    result["reasoning_trace"] = result.get("reasoning_trace", [])
    try:
        result["confidence"] = float(result.get("confidence", 0.5))
    except (TypeError, ValueError):
        result["confidence"] = 0.5
    return result
