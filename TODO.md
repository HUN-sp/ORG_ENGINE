# Roadmap / status

North star: **reproduce the Reflexion learning curve on organizational questions, with an honest
ablation (memory off vs on) proving the memory is what improves answers.**

## Done
- [x] Core loop: retrieve → answer → score → gap analysis → lesson → re-run (V1/V2).
- [x] Memory (lesson store), evaluator (deterministic evidence coverage + LLM judge).
- [x] Providers: Groq / Ollama / offline mock.
- [x] **Honest ablation harness** (`experiment.py`): cold (no memory) vs warm (learning),
      first-attempt scoring, learning-curve dashboard.
- [x] **Fresh-incident dataset**: undocumented incidents (Q-006 OOM, Q-007 login latency) with
      NO postmortem — root cause must be investigated from the recent commit + guideline.
- [x] **Two-hop, recency-aware retrieval**: cold finds the symptom+commit but misses the guideline;
      a learned lesson triggers a second hop (commit content → related guideline). Generalizes
      across incident types (migration / cache / hot-path).

## Next (high value)
- [ ] **Run `experiment.py` on the real LLM** and record the actual cold-vs-warm curve. Capture a
      screenshot of the dashboard for the demo/one-pager. (Mock already validates the plumbing.)
- [ ] **Fail-gracefully question**: add a question whose evidence is genuinely missing; show the
      system lowers confidence and says "insufficient evidence" instead of hallucinating.
- [ ] Update `ONE_PAGER.md` results table with the real numbers once captured.

## Later (rigor / polish)
- [ ] Second similarity signal: local embeddings (sentence-transformers) alongside the LLM judge.
- [ ] Lesson lifecycle: auto-retire lessons with a low wins/uses ratio; de-duplicate near-identical
      lessons.
- [ ] Evidence graph: visualize ticket ↔ commit ↔ doc links behind a root cause.
- [ ] Larger eval set + a second "expert" to measure judge/expert agreement.

## Known limitations (state these honestly in the demo)
- Keyword retrieval on a small corpus; recency + two-hop compensate but embeddings would be more
  robust at scale.
- LLM-as-judge variance; mitigated by the deterministic evidence-coverage metric.
- Free Groq tier ~12k tokens/min — full `experiment.py` runs are throttled (auto-retry handles it).
