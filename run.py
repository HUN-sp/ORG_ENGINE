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

from engine import config, pipeline
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

    r = pipeline.process_question(question, expert, retriever, memory)
    v1, v2 = r["v1"], r["v2"]

    print(f'Lessons available before answering (Mode B): {r["lessons_available_at_v1"]}')
    print(f'Retrieved evidence (v1): {[e["id"] for e in r["evidence_v1"]]}')
    print(f'\n-- ANSWER v1 (confidence {v1["confidence"]}) --\n{v1["answer"]}')
    print(f'v1 scores: {v1["scores"]}')
    print(f'\n-- HUMAN EXPERT ANSWER ({r["human"]["expert"]}) --\n{r["human"]["answer"]}')
    print(f'\nGap analysis: missed evidence {r["gap"]["missing_evidence"]}; '
          f'root_cause_found={r["gap"]["root_cause_found"]}')
    print(f'Learned lesson {r["lesson"]["id"]}: {r["lesson"]["reasoning_rule"]}')
    print(f'Retrieved evidence (v2): {[e["id"] for e in r["evidence_v2"]]}')
    print(f'\n-- ANSWER v2 (confidence {v2["confidence"]}) --\n{v2["answer"]}')
    print(f'v2 scores: {v2["scores"]}')
    print(f'\n>>> LEARNING GAIN: {v1["scores"]["overall"]} -> {v2["scores"]["overall"]}  (Δ {r["gain"]:+})')

    return {
        "question_id": q["id"],
        "difficulty": q.get("difficulty", ""),
        "tests_generalization_of": q.get("tests_generalization_of"),
        "seconds": round(time.time() - t0, 1),
        **r,
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
