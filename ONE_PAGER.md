# One-Pager — Expert-Learning Organizational Reasoning Engine

**Project:** INT-AI-01 · **Author:** Mayank Vashisht

## Problem
Teams have docs, tickets, Slack, and code — yet people still ask a few experts "why was the release
delayed?" / "what caused this incident?". Plain AI assistants **retrieve facts but miss causality**
and don't improve. We built an engine that reasons like a senior engineer, is corrected by a human
expert, and **measurably improves** on the next attempt — with **no model fine-tuning**.

## Approach (grounded in two papers)
- **Reflexion** (arXiv:2303.11366) — convert the correction into a *verbal lesson*, store it in
  **episodic memory**, inject it into future answers. The model is frozen; the **memory** is the
  thing that learns.
- **Self-Refine** (arXiv:2303.17651) — same model generates → critiques → refines. Drives the
  **V1→V2** re-answer.
- **Our adaptation:** neither paper has a human expert. Here the **human answer is the reward
  signal**, and the **gap analysis is the self-reflection step**.

## Architecture
```
question ─► Retriever (lesson-aware) ─► Actor (LLM) ─► answer + reasoning trace + cited evidence
                                              │
human expert answer ─► Reflector ─► gap analysis ─► LESSON ─► Memory ─┐
                                                                      │ (recalled next time)
                          re-run with lesson ─► Version 2 ◄───────────┘
Evaluator scores every answer vs. the human answer (gold).
```
Components: `retriever` (keyword + tag + lesson-driven query expansion), `actor`, `evaluator`,
`reflector`, `memory` (the lesson store), behind a swappable `llm_client` (Groq / Ollama / mock).

## Two kinds of learning
1. **Within a question (Self-Refine):** the gap vs. the expert → a lesson → a better V2.
2. **Across questions (Reflexion):** a lesson from Q-001 improves the **first** answer to the
   unseen Q-002. **Observed:** Q-002 started at overall **80** at V1 because `LSN-001` was already
   in memory — generalization, not memorization.

## What makes it more than RAG
Plain RAG retrieves the same documents forever. Here a lesson ("for failure questions, trace to the
triggering commit and check the violated guideline") **changes retrieval itself** — V2 surfaced
`WIKI-migrations` and the fix commit that the bare question could not reach.

## Results (real run, Groq Llama-3.3-70B, synthetic DevOps dataset)
| Question | V1 overall | V2 overall | Notes |
|---|---|---|---|
| Q-001 "why was v4.2.0 delayed?" | 75 | 80 | root cause matched; evidence coverage 0.50 → 0.67 |
| Q-002 "payments latency spike" (unseen) | **80** | 75 | **generalized** from LSN-001 at V1 |
| Q-003 ownership | 80 | 80 | single-hop, already strong (control) |
| Q-004 Postgres vs DynamoDB | 65 | — | ADR question (control) |

**Key finding on measurement:** once memory is populated, later questions *start* strong at V1, so
the 20% target shows up as **a rising V1 baseline across questions** (generalization), not only as a
within-question V1→V2 jump. Deterministic **evidence coverage** corroborates the LLM-judge scores.

## Assumptions
- All data is synthetic (no real/sensitive data). Human answers are ground truth.
- Slack is a JSON feed. Any free LLM is acceptable (used Groq free tier; Ollama for offline).
- No fine-tuning, auth, or production integration (out of scope per the brief).

## Limitations
- LLM-as-judge variance — mitigated by a deterministic evidence-coverage metric.
- Small synthetic corpus — keyword retrieval suffices; embeddings unnecessary at this scale.
- Free-tier token/min rate limits slow full-feed runs (handled with auto-retry).

## What I'd build next
1. **Embeddings + reranking** when the corpus grows (vocabulary mismatch, e.g. "slow" vs "p99").
2. **Lesson lifecycle** — auto-retire lessons whose `wins/uses` ratio is low; merge duplicates.
3. **A real evidence graph** linking ticket↔commit↔doc for multi-hop root-cause tracing.
4. **Confidence calibration** + routing low-confidence answers to a human automatically.
5. **A larger eval set** with multiple experts to measure inter-rater agreement and robustness.
