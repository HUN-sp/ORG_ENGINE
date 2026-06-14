"""Reflector (Reflexion M_sr) — the gap analysis + lesson creation step.

This is the project's core adaptation of Reflexion: the 'reward' is the HUMAN
expert answer, and the verbal self-reflection is a structured comparison of the
AI answer against it. The output is a reusable LESSON (specific + actionable,
as Self-Refine §4 requires) stored in long-term memory.
"""
from __future__ import annotations
from .llm_client import llm_json


def _deterministic_missing_evidence(ai: dict, expert: dict) -> list[str]:
    used = {e.strip().lower() for e in ai.get("evidence_used", [])}
    return [g for g in expert.get("gold_evidence", []) if g.strip().lower() not in used]


def gap_analysis(question: str, ai: dict, expert: dict) -> dict:
    missing_evidence = _deterministic_missing_evidence(ai, expert)
    prompt = f"""Compare an AI answer to an expert's ground-truth answer and diagnose the gaps.

QUESTION: {question}

AI ANSWER: {ai['answer']}
AI ROOT CAUSE: {ai.get('root_cause','N/A')}
AI REASONING TRACE: {ai.get('reasoning_trace', [])}
AI EVIDENCE USED: {ai.get('evidence_used', [])}

EXPERT ANSWER: {expert['answer']}
EXPERT ROOT CAUSE: {expert.get('root_cause','N/A')}
EXPERT REASONING PATTERN: {expert.get('reasoning_pattern', [])}
EXPERT GOLD EVIDENCE: {expert.get('gold_evidence', [])}
EVIDENCE THE AI MISSED (computed): {missing_evidence}

Return JSON:
{{
  "reasoning_gaps": ["specific reasoning steps the AI skipped vs the expert"],
  "root_cause_found": <true|false>,
  "factual_errors": ["any wrong claims the AI made"],
  "what_ai_missed": "one-sentence summary of the core miss"
}}"""
    g = llm_json(prompt)
    g["missing_evidence"] = missing_evidence
    g.setdefault("reasoning_gaps", [])
    g.setdefault("factual_errors", [])
    g.setdefault("root_cause_found", False)
    g.setdefault("what_ai_missed", "")
    return g


def make_lesson(question: str, ai: dict, expert: dict, gap: dict) -> dict:
    """Distil the gap into a reusable, generalizable lesson (not the answer itself)."""
    prompt = f"""Turn this correction into a REUSABLE lesson that will help answer FUTURE, similar
questions of the same TYPE. Do NOT encode the specific answer — encode the reasoning pattern.

QUESTION: {question}
WHAT THE AI MISSED: {gap.get('what_ai_missed','')}
REASONING GAPS: {gap.get('reasoning_gaps', [])}
EVIDENCE THE AI MISSED: {gap.get('missing_evidence', [])}
EXPERT REASONING PATTERN: {expert.get('reasoning_pattern', [])}

Return JSON with EXACTLY these fields:
{{
  "trigger_pattern": "short phrase describing the TYPE of question this applies to (e.g. 'why did X fail or get delayed')",
  "tags": ["3-6 lowercase keywords for retrieval"],
  "what_ai_missed": "{gap.get('what_ai_missed','')}",
  "reasoning_rule": "an actionable rule: the reasoning steps to follow next time",
  "evidence_rule": "which source TYPES to always cross-reference for this question type",
  "confidence_adjustment": "when to lower confidence for this question type"
}}"""
    lesson = llm_json(prompt)
    lesson["created_from_question"] = question
    lesson.setdefault("tags", [])
    return lesson
