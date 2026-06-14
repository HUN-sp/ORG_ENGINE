"""End-to-end run loop — the full learning cycle for every question in the feed.

For each question:
  1. retrieve evidence + recall relevant lessons (lessons from EARLIER questions
     already help here -> this is Reflexion Mode B / generalization)
  2. Actor drafts ANSWER v1, scored against the human answer
  3. human answer revealed; Reflector does gap analysis + writes a LESSON
  4. Actor re-answers WITH the new lesson -> ANSWER v2 (Self-Refine Mode A)
  5. score v2, log the gain, plot later with dashboard.py

Usage:
  python run.py                 # run the whole feed
  python run.py --question Q-001
  python run.py --keep-memory   # don't wipe lessons first (to show accumulation)
"""
from __future__ import annotations
import argparse
import json
import sys
import time

from engine import config, actor, evaluator, reflector
from engine.retriever import Retriever
from engine.memory import Memory


def load_questions():
    return json.loads(config.QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]


def load_ground_truth():
    answers = json.loads(config.GROUND_TRUTH_FILE.read_text(encoding="utf-8"))["answers"]
    return {a["question_id"]: a for a in answers}


def banner(text):
    print("\n" + "=" * 72 + f"\n{text}\n" + "=" * 72)


# Windows consoles default to cp1252 and choke on unicode; force UTF-8 stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_one(q, expert, retriever, memory):
    question = q["text"]
    banner(f'{q["id"]}  ·  {question}')
    t0 = time.time()

    # 1. recall (retrieval is lesson-aware: lessons from EARLIER questions already
    #    sharpen this search -> Reflexion Mode B / generalization)
    lessons_v1 = memory.retrieve(question)
    evidence_v1 = retriever.retrieve(question, lessons=lessons_v1)
    print(f'Lessons available before answering (Mode B): {[l["id"] for l in lessons_v1]}')
    print(f'Retrieved evidence (v1): {[d.id for d in evidence_v1]}')

    # 2. Version 1
    v1 = actor.answer(question, evidence_v1, lessons_v1)
    s1 = evaluator.score(v1, expert)
    print(f'\n-- ANSWER v1 (confidence {v1["confidence"]}) --\n{v1["answer"]}')
    print(f'v1 scores: {s1}')

    # 3. human-in-the-loop + gap analysis + lesson
    print(f'\n-- HUMAN EXPERT ANSWER ({expert["expert"]}) --\n{expert["answer"]}')
    gap = reflector.gap_analysis(question, v1, expert)
    print(f'\nGap analysis: missed evidence {gap["missing_evidence"]}; '
          f'root_cause_found={gap["root_cause_found"]}')
    lesson = reflector.make_lesson(question, v1, expert, gap)
    lesson = memory.add(lesson)
    print(f'Learned lesson {lesson["id"]}: {lesson["reasoning_rule"]}')

    # 4. Version 2 (re-run WITH the new lesson — note retrieval is now lesson-aware,
    #    so v2 can surface evidence the bare question could not reach)
    lessons_v2 = memory.retrieve(question)
    evidence_v2 = retriever.retrieve(question, lessons=lessons_v2)
    print(f'Retrieved evidence (v2): {[d.id for d in evidence_v2]}')
    v2 = actor.answer(question, evidence_v2, lessons_v2)
    s2 = evaluator.score(v2, expert)
    print(f'\n-- ANSWER v2 (confidence {v2["confidence"]}) --\n{v2["answer"]}')
    print(f'v2 scores: {s2}')

    gain = round(s2["overall"] - s1["overall"], 1)
    memory.record_use([lesson["id"]], won=gain > 0)
    print(f'\n>>> LEARNING GAIN: {s1["overall"]} -> {s2["overall"]}  (Δ {gain:+})')

    return {
        "question_id": q["id"],
        "question": question,
        "difficulty": q.get("difficulty", ""),
        "tests_generalization_of": q.get("tests_generalization_of"),
        "lessons_available_at_v1": [l["id"] for l in lessons_v1],
        "evidence_retrieved_v1": [d.id for d in evidence_v1],
        "evidence_retrieved_v2": [d.id for d in evidence_v2],
        "gold_evidence": expert.get("gold_evidence", []),
        "v1": {**v1, "scores": s1},
        "v2": {**v2, "scores": s2},
        "gap_analysis": gap,
        "lesson_id": lesson["id"],
        "gain": gain,
        "seconds": round(time.time() - t0, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", help="run a single question id, e.g. Q-001")
    ap.add_argument("--keep-memory", action="store_true",
                    help="do not wipe lessons before running")
    args = ap.parse_args()

    questions = load_questions()
    gt = load_ground_truth()
    retriever = Retriever()
    memory = Memory()
    if not args.keep_memory:
        memory.reset()
        print("Memory reset (starting with zero lessons).")

    if args.question:
        questions = [q for q in questions if q["id"] == args.question]

    log = []
    for q in questions:
        if q["id"] not in gt:
            print(f'(skipping {q["id"]} — no ground truth)')
            continue
        log.append(run_one(q, gt[q["id"]], retriever, memory))

    config.RUN_LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")
    banner("SUMMARY")
    for e in log:
        tag = "  (generalization test)" if e.get("tests_generalization_of") else ""
        print(f'{e["question_id"]}: {e["v1"]["scores"]["overall"]:5} -> '
              f'{e["v2"]["scores"]["overall"]:5}  (Δ {e["gain"]:+}){tag}')
    if log:
        avg_gain = round(sum(e["gain"] for e in log) / len(log), 1)
        print(f'\nAverage learning gain: {avg_gain:+} points   (target ≥20)')
    print(f'\nRun log written to {config.RUN_LOG_FILE}')
    print("Dashboard:  streamlit run dashboard.py")


if __name__ == "__main__":
    main()
