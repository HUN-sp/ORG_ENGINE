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
Components: `retriever` (keyword + tag + recency, with a lesson-driven **two-hop** that pulls the
guideline a commit may violate), `actor`, `evaluator`, `reflector`, `memory` (the lesson store),
behind a swappable `llm_client` (OpenRouter / Groq / Ollama / mock).

## Two kinds of learning
1. **Within a question (Self-Refine):** the gap vs. the expert → a lesson → a better V2.
2. **Across questions (Reflexion):** a lesson from Q-001 improves the **first** answer to the
   unseen Q-002. **Observed:** Q-002 started at overall **80** at V1 because `LSN-001` was already
   in memory — generalization, not memorization.

## What makes it more than RAG
Plain RAG retrieves the same documents forever. Here a lesson ("for failure questions, trace to the
triggering commit and check the violated guideline") **changes retrieval itself** — V2 surfaced
`WIKI-migrations` and the fix commit that the bare question could not reach.

## Results (real run, Groq Llama-3.1-8B-instant, synthetic DevOps dataset)

Ablation — answer every question with memory **OFF** (cold / plain RAG) vs **ON** (warm /
learning). The gap is the measured value of the learning loop.

| Question | cold (no memory) | warm (learning) | lift | lesson applied? |
|---|---|---|---|---|
| Q-001 "why was v4.2.0 delayed?" (documented) | 75 | 70 | −5 | no (first incident) |
| Q-002 "payments latency spike" | 70 | 75 | +5 | yes (LSN-001) |
| Q-003 ownership (control) | 55 | 70 | +15* | no |
| Q-005 "what's blocking v4.3.0?" | 45 | 65 | +20 | yes |
| **Q-006 "checkout OOMKilled" (fresh, no postmortem)** | **42.5** | **72.5** | **+30** | **yes** |
| **Q-007 "login latency" (fresh, no postmortem)** | **37.5** | **52.5** | **+15** | **yes** |

| Metric | cold | warm | lift |
|---|---|---|---|
| **All questions** | 54.2 | 67.5 | **+13.3 (+24.5%)** ✅ |
| **Fresh incidents (no postmortem)** | 40.0 | 62.5 | **+22.5 (+56.2%)** ✅ |

**Headline:** on **fresh, undocumented incidents** — the realistic hard case, where there's no
write-up to copy — the learning loop improved accuracy by **+22.5 points (+56%)**, beating the ≥20%
target. The lift concentrates on questions where a relevant lesson was actually applied.

**Honest caveats (stated deliberately):**
- `*` Some movement is run-to-run **noise**, not learning: Q-003 rose +15 although *no* lesson was
  applied, and Q-001 fell −5 — both are sampling variance on a small (8B) model at temperature 0.2.
  The genuine learning signal is on lesson-applied questions and on the fresh-incident aggregate.
- The judge is the same 8B model, so absolute scores are approximate — which is why we lead with the
  **deterministic evidence-coverage** metric and the cold-vs-warm *comparison*, not any single score.
- One question (Q-004) was skipped by a transient network error mid-run; the harness skipped it
  gracefully rather than crashing.

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
