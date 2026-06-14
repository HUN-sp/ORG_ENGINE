# Learning Loop & Memory Architecture
### Expert-Learning Organizational Reasoning Engine (INT-AI-01)

This document describes **how the system learns** — grounded in two papers:

- **Reflexion** (Shinn et al., 2023, arXiv:2303.11366) — verbal reinforcement: convert a reward
  signal into *language* feedback, store it in **episodic memory**, inject it into the next attempt.
  No weight updates.
- **Self-Refine** (Madaan et al., 2023, arXiv:2303.17651) — the *same* model generates →
  critiques → refines, **iterating within a single task**. Feedback must be **specific and actionable**.

> **The one-line idea:** The model never changes. What changes is a growing notebook of *lessons*
> distilled from being corrected by humans. The system retrieves the relevant lessons before it
> answers, so it gets better over time without any training.

---

## 1. Why this is NOT reinforcement learning (and what it is instead)

The assignment explicitly puts fine-tuning/retraining **out of scope**. So "learning" here is
**memory-augmented in-context learning**, exactly the Reflexion paradigm:

| Traditional RL | Our system (Reflexion-style) |
|---|---|
| Updates model weights via gradients | Weights frozen — LLM is a fixed reasoning engine |
| Reward = scalar | "Reward" = the human expert's answer (rich, textual) |
| Learns over millions of samples | Learns over a handful of corrections |
| Opaque | Every lesson is human-readable text |

The "policy" the agent improves is its **memory** (`mem`), not its parameters
(Reflexion §3: *"parameterizes a policy as an agent's memory"*).

---

## 2. The two learning modes (we use both)

```
                 ┌─────────────────────────────────────────────┐
                 │  MODE A — Self-Refine (within ONE question)   │
                 │  Drives the V1 → V2 demo                       │
                 └─────────────────────────────────────────────┘
   Question ─► Actor ─► Evaluator ─► Self-Reflection ─► Actor (refine) ─► better answer
                  ▲                                          │
                  └────────────── iterate ───────────────────┘

                 ┌─────────────────────────────────────────────┐
                 │  MODE B — Reflexion (ACROSS questions)        │
                 │  Drives "the 50th answer beats the 1st"       │
                 └─────────────────────────────────────────────┘
   Lesson from Q1's correction ─► stored in long-term memory ─► retrieved for Q2, Q7, Q50…
```

- **Mode A (Self-Refine)** is what the deliverable literally asks for: re-run a question and show
  Version 2 > Version 1. The trigger to refine is the **gap analysis vs. the human answer**.
- **Mode B (Reflexion)** is the part that proves *real* learning: a lesson learned on one question
  improves answers to **new, similar questions** it has never seen. This is the headline.

> **Important distinction for the demo.** Re-answering the *exact same* question better is cheap
> (you could just cache the human answer). The convincing result is **generalization** — a lesson
> from "Why was v4.2.0 delayed?" makes the *first* answer to "Why did payments latency spike?"
> better, because both need the same reasoning pattern (symptom → triggering commit → violated guideline).

---

## 3. Component model (mirrors Reflexion's Actor / Evaluator / Self-Reflection)

| Component | Reflexion name | What it does here | Input → Output |
|---|---|---|---|
| **Retriever** | (env) | Searches the 4 knowledge sources (wiki, tickets, Slack, repo) | query → evidence chunks |
| **Actor** | `M_a` | Drafts an answer + **reasoning trace** + confidence, using retrieved evidence **and** retrieved lessons | question + evidence + lessons → answer |
| **Evaluator** | `M_e` | Scores the answer. **V1 self-estimate**, then **vs. human answer** (gold) | answer (+ human answer) → scores |
| **Reflector** | `M_sr` | The **gap analysis**: compares AI vs human, writes a specific, actionable **lesson** | AI answer + human answer + trace → lesson |
| **Memory** | `mem` | Stores lessons (long-term) + current trajectory (short-term) | lesson → retrievable store |

All five can be the **same** LLM (Claude) with different prompts — Self-Refine §2 shows one model
can play generator, critic, and refiner.

---

## 4. The full loop (end to end)

```
(1) INGEST     A question arrives from the simulated Slack feed.
                  │
(2) RECALL     Retrieve (a) evidence from sources, (b) relevant LESSONS from memory.
                  │            └── Mode B kicks in here: past lessons shape THIS answer.
(3) REASON     Actor drafts ANSWER v1 + reasoning trace + evidence list + confidence.
                  │
(4) SELF-EVAL  Evaluator scores v1 against itself (Self-Refine feedback).
               If a human answer is NOT yet available → optionally self-refine (Mode A) and stop.
                  │
(5) HUMAN      Expert provides the ground-truth answer (the "reward").
                  │
(6) GAP        Reflector compares AI v1 vs human:
                  • missing_evidence   (sources the expert used, AI didn't)
                  • reasoning_gaps     (causal steps AI skipped)
                  • root_cause_delta   (did AI find the true root cause?)
                  • factual_errors
                  │
(7) LEARN      Reflector distills a LESSON (specific + actionable) → store in long-term memory.
                  │
(8) RE-RUN     Actor re-answers the SAME question WITH the new lesson injected → ANSWER v2.
                  │
(9) MEASURE    Score v1 and v2 against the human answer. Assert v2 > v1 (target ≥20% gain).
                  │
(10) TREND     Append both scores to the run log → dashboard shows accuracy rising over questions.
```

Steps (5)→(8) are the **human-in-the-loop feedback cycle**. Step (2)'s lesson-recall is what makes
question N+1 start smarter than question N.

---

## 5. Memory architecture

Two tiers, exactly as Reflexion §3 ("short-term and long-term memory"):

### 5.1 Short-term memory — the trajectory
Lives only for one question. Holds the retrieved evidence, the v1 answer, the reasoning trace, and
the gap analysis. Discarded (or archived to the run log) after the question is resolved.

### 5.2 Long-term memory — the lesson store
Persistent across questions. This is the "notebook" that grows. **Bounded retrieval**: like
Reflexion (memory size Ω ≈ 1–3), we inject only the **top-K most relevant lessons** (K=3) into the
Actor prompt, so the context never blows up and stays on-topic.

**Lesson schema** (`data/memory/lessons.json` — one object per lesson):

```json
{
  "id": "LSN-001",
  "created_from_question": "Q-001",
  "trigger_pattern": "why was <release|deploy> delayed / why did <service> fail",
  "tags": ["root-cause", "release", "deploy", "database"],
  "what_ai_missed": "Stopped at the symptom (checkout error spike) and never traced it to the code change that caused it.",
  "reasoning_rule": "For 'why did X fail/get delayed' questions, trace the causal chain: symptom → the deploy/commit that introduced it (search commits near the incident time) → whether it violated a documented guideline (search the wiki).",
  "evidence_rule": "Always cross-reference: incident ticket + Slack incident thread + the triggering commit + the relevant wiki guideline. An answer citing only the Slack thread is incomplete.",
  "confidence_adjustment": "If the triggering commit cannot be found, lower confidence and say so — do not assert a root cause.",
  "uses": 0,
  "wins": 0
}
```

- `reasoning_rule` and `evidence_rule` are the **actionable, specific** feedback Self-Refine §4
  shows is essential (generic feedback barely helps).
- `uses`/`wins` let you **retire** lessons that never improve answers (quality control).

### 5.3 Retrieval of lessons
Embed each lesson's `trigger_pattern` + `tags`; at query time, embed the question and pull the
top-K by similarity (a keyword/tag overlap match is a fine v1 — no vector DB required). Inject as:

```
RELEVANT LESSONS FROM PAST CORRECTIONS (apply these):
1. <reasoning_rule>
2. <evidence_rule>
...
```

---

## 6. How "learning" is measured (the part the company actually grades)

Anyone can wire up RAG. The differentiator is **proving** improvement. Define metrics up front and
score every answer **against the human answer** as gold:

| Metric | How computed | Target |
|---|---|---|
| **Answer similarity** | LLM-as-judge (0–100) "how close is AI answer to expert answer in substance" + embedding cosine as a sanity check | ≥75% |
| **Root-cause match** | Judge: does AI's stated root cause equal the expert's `root_cause`? (0/1) | ≥70% |
| **Evidence coverage** | `|AI_cited ∩ gold_evidence| / |gold_evidence|` (exact, deterministic — this is why gold_evidence IDs are in the dataset) | ≥80% |
| **Learning gain** | `score_v2 − score_v1` per question, averaged | ≥20% |
| **Response time** | wall clock | <15s |
| **Scenario coverage** | answered / total defined questions | 100% |

`evidence_coverage` is deliberately **deterministic** (set overlap on source IDs) so you have at
least one metric that isn't another LLM's opinion. Pair it with the LLM-judge similarity for
robustness — Self-Refine §3.2 uses exactly this mix (task metric + LLM-pref + human-pref).

---

## 7. Why answers improve — the causal story for your one-pager

1. **V1 answer** (no relevant lessons yet) is shallow: it retrieves the obvious source (the Slack
   thread), reports the **symptom**, and stops. Low root-cause match, partial evidence coverage.
2. **Human answer** supplies the true causal chain and the sources an expert actually used.
3. **Gap analysis** names precisely what was missed (the triggering commit + the violated guideline).
4. **Lesson** encodes the *reasoning pattern*, not the answer: "trace symptom → commit → guideline."
5. **V2** (same question, lesson injected) now retrieves the commit + wiki and produces the full
   chain → higher similarity, root-cause match, evidence coverage. **Measured gain.**
6. **Generalization**: the *next* incident question inherits the same lesson and is better on its
   **first** try — the Reflexion learning curve (paper Fig. 3: sharp jump after the first trials).

---

## 8. Failure-graceful behavior (Design Principle: "fail gracefully")

- If retrieval finds no triggering commit, the Actor must **lower confidence** and state the gap,
  not invent a root cause (the `confidence_adjustment` field enforces this).
- The Evaluator flags low-confidence answers for human review rather than auto-accepting.
- Lessons with `wins/uses` ratio below a threshold are flagged for retirement, so bad lessons don't
  compound.

---

## 9. Minimal tech stack (60-hour scope) — free / open-source only

The system is **LLM-agnostic**: every component calls a single adapter `llm(prompt) -> str`, so the
provider is a one-line config change. No paid API is required.

- **Python** orchestrator (one file per component: `retriever.py`, `actor.py`, `evaluator.py`,
  `reflector.py`, `memory.py`) + an `llm_client.py` adapter.
- **LLM (free options)** — pick one behind the adapter:
  - *Hosted free tier (recommended, fast, no GPU):* **Groq** (Llama 3.3 70B), **Google Gemini**
    (Flash, free tier), **OpenRouter** (`:free` models), **Mistral** free tier.
  - *Fully local (offline, no account):* **Ollama** — `qwen2.5:7b`, `llama3.1:8b`, or `gemma2:9b`.
- **Judge caveat:** the V1→V2 improvement claim is only as trustworthy as the model scoring it. A
  small local model is a weak judge. Mitigation: (a) lean on the **deterministic** metrics —
  `evidence_coverage` is pure set-overlap on source IDs, root-cause match can be keyword-based, no
  LLM needed; (b) if possible, use a **70B free-tier model (Groq/Gemini) for the judge step only**,
  even if a smaller model does the answering. Mixing models per role is fine.
- **Retrieval / embeddings (free):** start with keyword + tag match over the JSON sources (no model
  at all). For semantic search, `sentence-transformers` (`all-MiniLM-L6-v2`) runs locally for free,
  or `nomic-embed-text` via Ollama. The dataset is small by design.
- **Storage**: plain JSON files (`lessons.json`, `run_log.json`). No database needed.
- **Dashboard**: a Streamlit page or a notebook plotting `score_v1` vs `score_v2` over questions.

---

## 10. Build order (de-risked)

1. Load sources + retriever (keyword match). Verify questions are answerable.
2. Actor → produces v1 + trace + evidence list. (No memory yet.)
3. Evaluator + deterministic evidence-coverage metric.
4. Wire human answers from `ground_truth/`. Gap analysis (Reflector).
5. Lesson creation + memory store + lesson injection.
6. Re-run → v2. Assert and log the gain. **← this is the demo moment.**
7. Run the full question feed; plot the trend. Add 1 generalization pair to prove Mode B.
8. README + one-pager + 3-min demo.

See `data/README.md` for how the mock dataset is wired so that **good answers require connecting
multiple sources** — that's what makes the gap analysis meaningful.
