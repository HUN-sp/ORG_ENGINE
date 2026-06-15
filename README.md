# Expert-Learning Organizational Reasoning Engine (INT-AI-01)

A small system that answers organizational questions the way a senior engineer would, gets corrected
by a human expert, and **measurably improves** afterward — **without any model fine-tuning**.

On fresh, undocumented incidents it improved root-cause accuracy by **+56%** (cold vs. warm
ablation, Groq Llama-3.1-8B), beating the project's ≥20% target. See `ONE_PAGER.md`.

## The core idea (30 seconds)
The LLM never changes. What grows is a **notebook of lessons** distilled from human corrections.
Before answering, the system retrieves the relevant lessons and uses them to investigate better.
It's **RAG + a learning loop** — RAG is the floor; the learning is the point. Two modes:
- **Self-Refine** → re-answer the *same* question better (the V1→V2 demo).
- **Reflexion** → a lesson learned on one incident improves *new, unseen* incidents (real learning).

## What's here
| File | What |
|---|---|
| `DESIGN.md` | Learning loop + memory architecture (grounded in Reflexion & Self-Refine). Read first. |
| `ONE_PAGER.md` | Architecture, assumptions, **real results**, what's next. |
| `VIDEO_SCRIPT.md` | ~9-min demo script mapped to the assignment flow. |
| `app.py` | **Interactive UI** — ask a question, watch it learn (the main demo). |
| `run.py` | CLI: the full V1→human→lesson→V2 cycle for one question. |
| `experiment.py` | The ablation that produces the cold-vs-warm learning curve. |
| `dashboard.py` | Standalone chart view of the experiment results. |
| `engine/` | `retriever, actor, evaluator, reflector, memory, pipeline, llm_client`. |
| `data/` | Synthetic *Northwind* DevOps dataset (4 sources, 7 questions, ground truth). See `data/README.md`. |

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # then add a free key (OpenRouter or Groq)

# Interactive UI — the main demo (pick a question, watch it get corrected & improve):
streamlit run app.py

# CLI: one question, full cycle:
python run.py --question Q-001

# The headline result — cold (no memory) vs warm (learning) ablation:
python experiment.py                              # full feed (~40 calls)
python experiment.py --questions Q-001,Q-006,Q-007  # focused subset (~18 calls, free-tier friendly)
```

**Providers** (set `LLM_PROVIDER` in `.env`, or switch live in the UI sidebar):
`openrouter` and `groq` = real answers on free tiers · `ollama` = local · `mock` = offline dummy
(no key, instant — for testing/demo). Free tiers rate-limit; the client throttles and retries so
runs survive it.

## Architecture at a glance

```
question ─► Retriever ─┐                         ┌─► Evaluator ─► scores (vs. human = gold)
   (lesson-aware,      │                         │
    two-hop)           ▼                         │
            Actor (LLM) ─► answer + reasoning trace + cited evidence + confidence
                       ▲                         │
   Memory (lessons) ───┘                         ▼
        ▲                         human answer ─► Reflector ─► gap analysis ─► LESSON ─► Memory
        └──────────────── re-run (V2) ◄──────────────────────────────────────────────────┘
```
A learned lesson does two things: it guides the Actor's reasoning, and it triggers a **second
retrieval hop** (inspect the recent commit → pull the guideline it may violate) that plain RAG skips.

## Demo path
Reset memory (UI sidebar) → run **Q-001** (it learns a lesson) → run **Q-006**, a fresh OOM incident
it's never seen: it already solves it at V1 by reusing the lesson. Then open the **Learning Curve**
tab (after `python experiment.py`) for the cold-vs-warm numbers. Full walkthrough in `VIDEO_SCRIPT.md`.

## Status
- [x] Learning loop + two-tier memory (Reflexion + Self-Refine)
- [x] Synthetic dataset: 4 sources, 7 questions (incl. fresh undocumented incidents), ground truth
- [x] `engine/` components + shared pipeline
- [x] CLI (`run.py`), ablation (`experiment.py`), interactive UI (`app.py`), dashboard
- [x] Providers: OpenRouter / Groq / Ollama / offline mock; rate-limit handling
- [x] Real run + measured result (+56% fresh incidents, +24.5% overall) → `ONE_PAGER.md`
- [x] One-pager + video script
- [ ] Record the video; optional polish (fail-gracefully question, temperature=0 reproducibility)
