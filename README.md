# Expert-Learning Organizational Reasoning Engine (INT-AI-01)

A small system that answers organizational questions the way a senior engineer would, gets corrected
by a human expert, and **measurably improves** on the next attempt — without any model fine-tuning.

## What's here so far
- **`DESIGN.md`** — the learning loop + memory architecture, grounded in **Reflexion**
  (arXiv:2303.11366) and **Self-Refine** (arXiv:2303.17651). Read this first.
- **`data/`** — a complete synthetic DevOps dataset (the *Northwind* org). See `data/README.md`.

## The core idea (30 seconds)
The LLM never changes. A growing **notebook of lessons** — distilled from human corrections —
changes. Before answering, the system retrieves the relevant lessons and injects them into the
prompt. Two learning modes:
- **Self-Refine** → re-answer the *same* question better (the V1→V2 deliverable).
- **Reflexion** → a lesson learned on one question improves *new, similar* questions (real learning).

## Status
- [x] Learning-loop & memory architecture designed (`DESIGN.md`)
- [x] Interconnected synthetic dataset (4 sources, 5 questions, ground truth)
- [x] `engine/` components: `retriever`, `actor`, `evaluator`, `reflector`, `memory`, `llm_client`
- [x] Run loop (`run.py`) + run log + lesson-aware retrieval
- [x] Dashboard (`dashboard.py`, V1 vs V2 trend)
- [x] Offline `mock` LLM provider (runs the whole loop with no API key)
- [ ] Real run with a free LLM (Groq / Ollama)
- [ ] 3-min demo + one-pager

## Run it

```bash
pip install -r requirements.txt

# 1) Smoke test — no API key needed (proves the plumbing):
LLM_PROVIDER=mock python run.py --question Q-001     # Windows PS: $env:LLM_PROVIDER="mock"; python run.py --question Q-001

# 2) Real run — copy .env.example to .env and add your free Groq key:
cp .env.example .env        # then paste GROQ_API_KEY=...
python run.py               # whole feed;  --question Q-001 for one;  --keep-memory to accumulate

# 3) Dashboard:
streamlit run dashboard.py
```

Provider is one env var: `LLM_PROVIDER=groq` (free hosted) or `ollama` (local) or `mock` (offline).

## Architecture at a glance

```
question ─► Retriever ─┐                         ┌─► Evaluator ─► scores (V1)
        (lesson-aware) │                         │
                       ▼                         │
            Actor (LLM) ─► answer + trace + cited evidence + confidence
                       ▲                         │
   Memory (lessons) ───┘                         ▼
        ▲                         human answer ─► Reflector ─► gap analysis ─► LESSON ─► Memory
        └──────────────── re-run (V2) ◄──────────────────────────────────────────────────┘
```

## Suggested build order / demo
See `DESIGN.md` §10. The demo moment: ask Q-001 → weak V1 → human answer → gap analysis →
lesson → improved V2 → show the measured gain → then ask Q-002 and show it's already better at V1
(generalization). The `mock` provider already reproduces this end-to-end.
