"""Learning-curve experiment — the honest proof that the MEMORY is what improves answers.

We answer the SAME question feed two ways and compare FIRST-ATTEMPT quality:

  COLD  (baseline / plain RAG): memory permanently OFF. The system never learns.
  WARM  (our system): memory ON. Each question's first attempt benefits from lessons
        learned on EARLIER questions (true cross-question generalization, Reflexion-style).
        After answering, the question is 'corrected' by the expert and a lesson is stored
        for the benefit of LATER questions.

The gap between the WARM and COLD curves = the measured value of the learning loop.
This is the ablation: turn memory off -> the curve goes flat.

    python experiment.py            # real LLM (set GROQ_API_KEY)
    LLM_PROVIDER=mock python experiment.py   # offline smoke test
"""
from __future__ import annotations
import json
import sys

from engine import config, actor, evaluator, reflector
from engine.retriever import Retriever
from engine.memory import Memory

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_questions():
    return json.loads(config.QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]


def load_ground_truth():
    answers = json.loads(config.GROUND_TRUTH_FILE.read_text(encoding="utf-8"))["answers"]
    return {a["question_id"]: a for a in answers}


def answer_once(question, expert, retriever, lessons):
    """One first-attempt answer + score, given whatever lessons are available."""
    evidence = retriever.retrieve(question, lessons=lessons)
    ans = actor.answer(question, evidence, lessons)
    s = evaluator.score(ans, expert)
    return ans, s, [d.id for d in evidence]


def run_cold(questions, gt, retriever):
    """Baseline: no memory, ever. This is what plain RAG gives you."""
    out = []
    for q in questions:
        if q["id"] not in gt:
            continue
        try:
            _, s, ev = answer_once(q["text"], gt[q["id"]], retriever, lessons=[])
        except Exception as e:
            print(f"  ! skip {q['id']} (cold): {str(e)[:80]}")
            continue
        out.append({"id": q["id"], "overall": s["overall"], "scores": s, "evidence": ev,
                    "lessons_used": []})
        print(f"  {q['id']} cold = {s['overall']}")
    return out


def run_warm(questions, gt, retriever, memory):
    """Our system: first attempt uses lessons from EARLIER questions; then we learn."""
    memory.reset()
    out = []
    for q in questions:
        if q["id"] not in gt:
            continue
        expert = gt[q["id"]]
        lessons = memory.retrieve(q["text"])                      # from PRIOR questions only
        try:
            ans, s, ev = answer_once(q["text"], expert, retriever, lessons)
        except Exception as e:
            print(f"  ! skip {q['id']} (warm): {str(e)[:80]}")
            continue
        out.append({"id": q["id"], "overall": s["overall"], "scores": s, "evidence": ev,
                    "lessons_used": [l["id"] for l in lessons]})
        print(f"  {q['id']} warm = {s['overall']}  (lessons: {[l['id'] for l in lessons]})")
        # human-in-the-loop correction -> store a lesson for FUTURE questions
        try:
            gap = reflector.gap_analysis(q["text"], ans, expert)
            lesson = reflector.make_lesson(q["text"], ans, expert, gap)
            memory.add(lesson)
        except Exception as e:
            print(f"  ! {q['id']} learned no lesson: {str(e)[:80]}")
    return out


def main():
    questions = load_questions()
    gt = load_ground_truth()
    retriever = Retriever()
    memory = Memory()

    print("Running COLD baseline (memory OFF)...")
    cold = run_cold(questions, gt, retriever)
    print("Running WARM system (memory ON, learning across questions)...")
    warm = run_warm(questions, gt, retriever, memory)

    cold_by = {r["id"]: r for r in cold}
    warm_by = {r["id"]: r for r in warm}
    rows = []
    for q in questions:
        if q["id"] not in cold_by or q["id"] not in warm_by:
            continue
        c, w = cold_by[q["id"]], warm_by[q["id"]]
        rows.append({
            "id": q["id"],
            "question": q["text"],
            "difficulty": q.get("difficulty", ""),
            "cold_overall": c["overall"],
            "warm_overall": w["overall"],
            "lift": round(w["overall"] - c["overall"], 1),
            "lessons_used_warm": w["lessons_used"],
            "cold_scores": c["scores"],
            "warm_scores": w["scores"],
        })

    config.EXPERIMENT_LOG_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f'{"question":10} {"COLD":>6} {"WARM":>6} {"lift":>6}   lessons used (warm)')
    print("=" * 72)
    for r in rows:
        print(f'{r["id"]:10} {r["cold_overall"]:6} {r["warm_overall"]:6} '
              f'{r["lift"]:+6}   {r["lessons_used_warm"]}')
    def summarize(label, group):
        if not group:
            return
        ca = round(sum(r["cold_overall"] for r in group) / len(group), 1)
        wa = round(sum(r["warm_overall"] for r in group) / len(group), 1)
        lf = round(wa - ca, 1)
        pc = round(100 * lf / ca, 1) if ca else 0
        print(f'{label:34} cold={ca:5}  warm={wa:5}  lift={lf:+5} ({pc:+}%)')

    print("=" * 72)
    summarize("ALL questions", rows)
    fresh = [r for r in rows if r["difficulty"] == "fresh-incident"]
    summarize("FRESH incidents (no postmortem)", fresh)
    print("(target: +20% learning improvement)")
    print(f'\nExperiment log -> {config.EXPERIMENT_LOG_FILE}')
    print("Dashboard:  streamlit run dashboard.py")


if __name__ == "__main__":
    main()
