# Mock Dataset — Northwind (synthetic DevOps org)

All data here is **synthetic** (Assumption 1–2). It models a fictional e-commerce platform,
*Northwind*, with five services and a small team. The dataset is intentionally small but
**interconnected**, so that good answers require linking *multiple* sources — which is what makes
the gap analysis and the learning loop meaningful.

## The four knowledge sources (matches the assignment's "Data & Resources")

| Source | File(s) | source_id scheme |
|---|---|---|
| Wiki / docs | `sources/wiki/*.md` | `WIKI-*` (in the HTML comment header of each file) |
| Issue tracker | `sources/tickets/issues.json` | ticket `id` (e.g. `NW-1098`) |
| Slack Q&A + chatter | `sources/slack/threads.json` | thread `id` (e.g. `SLK-001`) |
| Code repo | `sources/repo/commits.json` | commit `hash` (e.g. `a3f9c2`) |

## How the pieces interconnect (the two flagship incidents)

**Incident 1 — v4.2.0 release delay (Q-001, the demo question):**
```
NW-1042 (tag feature) ─► commit a3f9c2 (plain CREATE INDEX on orders)
        │                         │
        │                         ▼  during v4.2.0 deploy
SLK-001 (#incidents: checkout 40% errors, orders locked)
        │                         │
        ▼                         ▼
NW-1098 (postmortem: root cause = non-concurrent index) ◄─ violates ─ WIKI-migrations
        │
        ▼
commit b7e1d4 (CONCURRENTLY fix) ─► v4.2.1
```
The true root cause lives in the **commit + the wiki guideline**, not in the Slack thread (which
only shows the symptom). That gap is the point.

**Incident 2 — payments latency spike (Q-002, the generalization test):** same shape —
`NW-1120 → commit c4d8e1 (sync un-timed fraud call) → SLK-010 (symptom) → NW-1130 (root cause) →
violates WIKI-service-calls → commit d9a2f7 fix`. A system that learned the "symptom → commit →
guideline" pattern from Q-001 should nail Q-002 on its **first** try.

## Files the engine produces (not authored by hand)
- `memory/lessons.json` — grows as the system is corrected (starts empty).
- a run log (your code writes this) — per-question `score_v1`, `score_v2`, evidence coverage,
  timing — feeds the dashboard.

## Grading keys
`ground_truth/expert_answers.json` holds, per question: the expert answer, the `root_cause`, the
**`gold_evidence`** id list (deterministic evidence-coverage key), the expert's `reasoning_pattern`,
and `expected_v1_weakness` (what a no-memory answer usually misses — handy for the demo narration).
