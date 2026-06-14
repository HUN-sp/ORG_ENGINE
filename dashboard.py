"""Learning dashboard — V1 vs V2 accuracy per question + the metrics that matter.

    streamlit run dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

RUN_LOG = Path(__file__).parent / "data" / "run_log.json"

st.set_page_config(page_title="Org Reasoning Engine — Learning Dashboard", layout="wide")
st.title("🧠 Organizational Reasoning Engine — Learning Dashboard")

if not RUN_LOG.exists():
    st.warning("No run log yet. Run `python run.py` first.")
    st.stop()

log = json.loads(RUN_LOG.read_text(encoding="utf-8"))
rows = []
for e in log:
    rows.append({
        "question": e["question_id"],
        "V1": e["v1"]["scores"]["overall"],
        "V2": e["v2"]["scores"]["overall"],
        "gain": e["gain"],
        "similarity_V2": e["v2"]["scores"]["similarity"],
        "evidence_cov_V2": e["v2"]["scores"]["evidence_coverage"],
        "root_cause_V2": e["v2"]["scores"]["root_cause_match"],
        "seconds": e["seconds"],
        "generalization": bool(e.get("tests_generalization_of")),
    })
df = pd.DataFrame(rows)

# headline metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg learning gain", f'{df["gain"].mean():+.1f}', help="target ≥ +20")
c2.metric("Avg V2 similarity", f'{df["similarity_V2"].mean():.0f}%', help="target ≥ 75%")
c3.metric("Avg V2 evidence coverage", f'{df["evidence_cov_V2"].mean()*100:.0f}%', help="target ≥ 80%")
c4.metric("Root-cause hit rate (V2)", f'{df["root_cause_V2"].mean()*100:.0f}%', help="target ≥ 70%")

st.subheader("Answer quality: Version 1 vs Version 2")
st.bar_chart(df.set_index("question")[["V1", "V2"]])

st.subheader("Per-question detail")
st.dataframe(df, use_container_width=True)

gen = df[df["generalization"]]
if not gen.empty:
    st.subheader("🔁 Generalization (Reflexion Mode B)")
    st.write(
        "These questions were never seen before, but a lesson learned on an *earlier* "
        "question was available at V1. A high V1 here = the system generalized, not memorized."
    )
    st.dataframe(gen[["question", "V1", "V2"]], use_container_width=True)

with st.expander("Raw run log"):
    st.json(log)
