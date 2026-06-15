"""Interactive UI for the Organizational Reasoning Engine.

    streamlit run app.py

Tabs:
  • Ask & Learn   — pick a question, watch V1 -> human -> gap -> lesson -> V2 live
  • Learning Curve — the cold-vs-warm ablation (run `python experiment.py` first)
  • Memory         — the lessons the system has learned so far
  • Knowledge      — browse the synthetic data sources
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from engine import config, pipeline
from engine.retriever import Retriever
from engine.memory import Memory
from engine.sources import load_all

st.set_page_config(page_title="Org Reasoning Engine", layout="wide", page_icon="🧠")


# ---------- data loaders ----------
@st.cache_data
def questions():
    return json.loads(config.QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]


@st.cache_data
def ground_truth():
    a = json.loads(config.GROUND_TRUTH_FILE.read_text(encoding="utf-8"))["answers"]
    return {x["question_id"]: x for x in a}


@st.cache_resource
def retriever():
    return Retriever()


def memory():
    # not cached: it changes as the system learns
    return Memory()


# ---------- sidebar ----------
st.sidebar.title("🧠 Reasoning Engine")
provider = st.sidebar.radio(
    "LLM provider",
    ["groq", "mock", "ollama"],
    help="mock = offline, no API key (great for a smooth demo). groq = real answers.",
)
# config is read at call-time, so this switches the provider live
config.LLM_PROVIDER = provider
config.JUDGE_PROVIDER = provider

mem = memory()
st.sidebar.metric("Lessons learned", len(mem.lessons))
if st.sidebar.button("🗑️ Reset memory (start fresh)"):
    mem.reset()
    st.sidebar.success("Memory cleared.")
    st.rerun()
st.sidebar.caption("Tip: run Q-001 (it learns), then run Q-006 — it should already be "
                   "strong at V1. That's generalization.")

tab_ask, tab_curve, tab_mem, tab_src = st.tabs(
    ["💬 Ask & Learn", "📈 Learning Curve", "🧩 Memory", "📚 Knowledge"]
)


# ================= TAB: Ask & Learn =================
with tab_ask:
    st.header("Ask a question — watch it get corrected and improve")
    qs = questions()
    gt = ground_truth()
    labels = [f'{q["id"]} — {q["text"]}' for q in qs if q["id"] in gt]
    pick = st.selectbox("Question", labels)
    qid = pick.split(" — ")[0]
    q = next(x for x in qs if x["id"] == qid)

    if st.button("▶️ Run the learning cycle", type="primary"):
        with st.spinner(f"Investigating with provider='{provider}' …"):
            st.session_state["result"] = pipeline.process_question(
                q["text"], gt[qid], retriever(), mem
            )
        st.rerun()

    res = st.session_state.get("result")
    if res and res["question"] == q["text"]:
        v1, v2 = res["v1"], res["v2"]

        # headline gain
        c1, c2, c3 = st.columns(3)
        c1.metric("V1 score", v1["scores"]["overall"])
        c2.metric("V2 score", v2["scores"]["overall"], f'{res["gain"]:+}')
        c3.metric("Lessons used at V1", len(res["lessons_available_at_v1"]),
                  help="If >0, this answer already benefits from earlier corrections (generalization).")

        def scorebar(s):
            st.caption(f'similarity {s["similarity"]}%  ·  evidence coverage '
                       f'{int(s["evidence_coverage"]*100)}%  ·  root-cause '
                       f'{"✅" if s["root_cause_match"] else "❌"}  ·  overall {s["overall"]}')

        st.divider()
        st.subheader("① Version 1 — first attempt")
        if res["lessons_available_at_v1"]:
            st.info(f'Already applying earlier lessons: {res["lessons_available_at_v1"]}')
        st.write(v1["answer"])
        st.caption(f'**Root cause:** {v1.get("root_cause","N/A")}  ·  confidence {v1.get("confidence")}')
        scorebar(v1["scores"])
        with st.expander("Reasoning trace & cited evidence (V1)"):
            st.write("**Reasoning:**", v1.get("reasoning_trace", []))
            st.write("**Evidence cited:**", v1.get("evidence_used", []))
            st.write("**Evidence retrieved:**", [e["id"] for e in res["evidence_v1"]])

        st.subheader("② Human expert answer (ground truth)")
        st.success(res["human"]["answer"])
        st.caption(f'**Expert:** {res["human"]["expert"]}  ·  '
                   f'**Gold evidence:** {res["gold_evidence"]}')

        st.subheader("③ Gap analysis")
        gap = res["gap"]
        cols = st.columns(2)
        cols[0].write("**Evidence missed:**")
        cols[0].write(gap.get("missing_evidence", []))
        cols[1].write("**Reasoning gaps:**")
        cols[1].write(gap.get("reasoning_gaps", []))
        st.caption(f'Root cause found at V1: {"✅" if gap.get("root_cause_found") else "❌"}')

        st.subheader("④ Learning event — the lesson stored in memory")
        L = res["lesson"]
        st.warning(f'**{L["id"]} · reasoning rule:** {L.get("reasoning_rule","")}\n\n'
                   f'**evidence rule:** {L.get("evidence_rule","")}\n\n'
                   f'**when to lower confidence:** {L.get("confidence_adjustment","")}')

        st.subheader("⑤ Version 2 — re-run with the lesson")
        st.write(v2["answer"])
        st.caption(f'**Root cause:** {v2.get("root_cause","N/A")}  ·  confidence {v2.get("confidence")}')
        scorebar(v2["scores"])
        with st.expander("Evidence retrieved (V2) — note the lesson-driven second hop"):
            st.write([e["id"] for e in res["evidence_v2"]])

        st.divider()
        if res["gain"] > 0:
            st.success(f'📈 Measurable improvement: {v1["scores"]["overall"]} → '
                       f'{v2["scores"]["overall"]}  (+{res["gain"]})')
        else:
            st.info("V1 was already strong (often because an earlier lesson generalized to it). "
                    "The learning shows up across questions — see the Learning Curve tab.")


# ================= TAB: Learning Curve =================
with tab_curve:
    st.header("Does it actually learn? Cold vs Warm ablation")
    st.caption("COLD = memory off (plain RAG baseline). WARM = each question's first attempt "
               "uses lessons from earlier questions. The gap = the value of learning.")
    if config.EXPERIMENT_LOG_FILE.exists():
        exp = json.loads(config.EXPERIMENT_LOG_FILE.read_text(encoding="utf-8"))
        df = pd.DataFrame([{"question": r["id"], "COLD (no memory)": r["cold_overall"],
                            "WARM (learning)": r["warm_overall"], "lift": r["lift"]} for r in exp])
        cold_avg, warm_avg = df["COLD (no memory)"].mean(), df["WARM (learning)"].mean()
        pct = (warm_avg - cold_avg) / cold_avg * 100 if cold_avg else 0
        a, b, c = st.columns(3)
        a.metric("Avg COLD (baseline)", f"{cold_avg:.0f}")
        b.metric("Avg WARM (learned)", f"{warm_avg:.0f}", f"{warm_avg-cold_avg:+.0f}")
        c.metric("Learning lift", f"{pct:+.0f}%", help="target ≥ +20%")
        st.line_chart(df.set_index("question")[["COLD (no memory)", "WARM (learning)"]])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No experiment results yet. Run:  `python experiment.py`  (or "
                "`LLM_PROVIDER=mock python experiment.py` for an offline demo), then reload.")


# ================= TAB: Memory =================
with tab_mem:
    st.header("🧩 What the system has learned")
    st.caption("This is the 'notebook' — lessons distilled from human corrections. The LLM never "
               "changes; this grows.")
    mem2 = memory()
    if not mem2.lessons:
        st.info("No lessons yet. Run a question in the Ask & Learn tab.")
    for L in mem2.lessons:
        with st.expander(f'{L["id"]} — {L.get("trigger_pattern","")}  '
                         f'(used {L.get("uses",0)}×, helped {L.get("wins",0)}×)'):
            st.write("**Reasoning rule:**", L.get("reasoning_rule", ""))
            st.write("**Evidence rule:**", L.get("evidence_rule", ""))
            st.write("**Confidence:**", L.get("confidence_adjustment", ""))
            st.write("**Tags:**", L.get("tags", []))


# ================= TAB: Knowledge =================
with tab_src:
    st.header("📚 Knowledge sources (synthetic)")
    docs = load_all()
    kinds = {"wiki": "Wiki / docs", "ticket": "Issue tracker", "slack": "Slack", "commit": "Commits"}
    for k, label in kinds.items():
        group = [d for d in docs if d.type == k]
        st.subheader(f"{label} ({len(group)})")
        for d in group:
            with st.expander(f"{d.id} — {d.title}"):
                st.text(d.text)
