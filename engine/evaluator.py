"""Evaluator (Reflexion M_e) — scores an AI answer against the human ground truth.

Three signals, two of them deterministic so the 'measured improvement' claim
does not rest entirely on an LLM's opinion (see DESIGN.md §6):

  evidence_coverage  : |used ∩ gold| / |gold|            (deterministic, 0..1)
  root_cause_match   : 1 if AI root cause == expert's    (LLM judge, 0/1)
  similarity         : substance overlap with expert     (LLM judge, 0..100)

overall = 0.5*similarity + 30*evidence_coverage + 20*root_cause_match   (0..100)
"""
from __future__ import annotations
from .llm_client import llm_json


def evidence_coverage(used: list[str], gold: list[str]) -> float:
    if not gold:
        return 1.0
    used_set = {u.strip().lower() for u in used}
    gold_set = {g.strip().lower() for g in gold}
    hit = len(used_set & gold_set)
    return round(hit / len(gold_set), 3)


def _judge(ai: dict, expert: dict) -> dict:
    prompt = f"""You are grading an AI answer against an expert's ground-truth answer.

EXPERT ANSWER:
{expert['answer']}
EXPERT ROOT CAUSE: {expert.get('root_cause','N/A')}

AI ANSWER:
{ai['answer']}
AI ROOT CAUSE: {ai.get('root_cause','N/A')}

Grade strictly on SUBSTANCE, not wording. Return JSON:
{{
  "similarity": <0-100, how much of the expert's substance the AI captured>,
  "root_cause_match": <1 if the AI identified the same underlying root cause as the expert, else 0>,
  "missing_points": ["key facts the expert had that the AI lacked"]
}}"""
    j = llm_json(prompt, judge=True)
    j["similarity"] = max(0, min(100, float(j.get("similarity", 0))))
    j["root_cause_match"] = 1 if int(j.get("root_cause_match", 0)) == 1 else 0
    j.setdefault("missing_points", [])
    return j


def score(ai: dict, expert: dict) -> dict:
    cov = evidence_coverage(ai.get("evidence_used", []), expert.get("gold_evidence", []))
    j = _judge(ai, expert)
    overall = 0.5 * j["similarity"] + 30 * cov + 20 * j["root_cause_match"]
    return {
        "similarity": round(j["similarity"], 1),
        "evidence_coverage": cov,
        "root_cause_match": j["root_cause_match"],
        "overall": round(overall, 1),
        "missing_points": j["missing_points"],
    }
