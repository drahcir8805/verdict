"""
Rubric Dashboard — reads results/*.json and renders four views in Streamlit.

Run:
    streamlit run dashboard.py
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from eval_harness import RESULTS_DIR, compute_diff


def _parse_timestamp(name: str) -> datetime:
    return datetime.strptime(Path(name).stem, "%Y-%m-%dT%H-%M-%S")


@st.cache_data
def load_all_runs() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    payloads = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        with open(path) as f:
            payload = json.load(f)
        payload["_filename"] = path.name
        payloads.append(payload)
    return payloads


def _passed_mark(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def view_pass_rate_over_time(runs: list[dict]) -> None:
    st.header("Pass rate over time")

    latest = runs[-1]
    previous = runs[-2] if len(runs) >= 2 else None

    col1, col2, col3 = st.columns(3)
    col1.metric("Latest pass rate", f"{latest['pass_rate']:.0%}")
    if previous is not None:
        delta = latest["pass_rate"] - previous["pass_rate"]
        col2.metric("Δ vs previous", f"{delta:+.0%}")
    else:
        col2.metric("Δ vs previous", "—")
    col3.metric("Total runs", len(runs))

    chart_data = {
        "timestamp": [_parse_timestamp(r["_filename"]) for r in runs],
        "pass_rate": [r["pass_rate"] for r in runs],
    }
    st.line_chart(chart_data, x="timestamp", y="pass_rate")

    table_rows = [
        {
            "timestamp": r["timestamp"],
            "model": r["model"],
            "passed": f"{r['passed']}/{r['total']}",
            "pass_rate": f"{r['pass_rate']:.0%}",
        }
        for r in reversed(runs)
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)


def view_per_question_history(runs: list[dict]) -> None:
    st.header("Per-question history")

    all_questions = sorted({r["question"] for run in runs for r in run["results"]})
    question = st.selectbox("Question", all_questions)

    rows = []
    passes = 0
    total = 0
    for run in runs:
        match = next((r for r in run["results"] if r["question"] == question), None)
        if match is None:
            continue
        total += 1
        if match["passed"]:
            passes += 1
        rows.append(
            {
                "timestamp": run["timestamp"],
                "model": run["model"],
                "verdict": _passed_mark(match["passed"]),
                "reason": match["reason"],
                "answer": match["answer"],
            }
        )

    if total == 0:
        st.info("This question has no runs yet.")
        return

    st.metric(
        f"Passed {passes}/{total} runs",
        f"{passes / total:.0%}",
    )
    st.dataframe(list(reversed(rows)), use_container_width=True, hide_index=True)


def view_latest_run_detail(runs: list[dict]) -> None:
    st.header("Latest run detail")

    latest = runs[-1]
    st.write(
        f"**Model:** `{latest['model']}` · "
        f"**Timestamp:** `{latest['timestamp']}` · "
        f"**Pass rate:** {latest['passed']}/{latest['total']} ({latest['pass_rate']:.0%})"
    )

    for r in latest["results"]:
        title = f"[{_passed_mark(r['passed'])}] {r['question']}"
        with st.expander(title):
            st.markdown(f"**Reason:** {r['reason']}")
            st.markdown("**Answer:**")
            st.code(r["answer"], language="markdown")


def view_run_vs_run_diff(runs: list[dict]) -> None:
    st.header("Run-vs-run diff")

    if len(runs) < 2:
        st.info("Need at least two runs to diff. Run the eval again.")
        return

    filenames = [r["_filename"] for r in runs]
    by_filename = {r["_filename"]: r for r in runs}

    col1, col2 = st.columns(2)
    before_name = col1.selectbox("Before", filenames, index=len(filenames) - 2)
    after_name = col2.selectbox("After", filenames, index=len(filenames) - 1)

    before = by_filename[before_name]
    after = by_filename[after_name]
    diff = compute_diff(before, after)

    delta = diff["delta"]
    st.metric(
        "Pass rate",
        f"{after['pass_rate']:.0%}",
        f"{delta:+.0%} vs {before['pass_rate']:.0%}",
    )

    with st.expander(f"Regressions ({len(diff['regressions'])})", expanded=True):
        if not diff["regressions"]:
            st.write("_none_")
        for r in diff["regressions"]:
            st.markdown(f"- **{r['question']}**")
            st.markdown(f"  - `{r['reason']}`")

    with st.expander(f"Improvements ({len(diff['improvements'])})", expanded=True):
        if not diff["improvements"]:
            st.write("_none_")
        for r in diff["improvements"]:
            st.markdown(f"- {r['question']}")

    with st.expander(f"Unchanged ({len(diff['unchanged'])})"):
        for r in diff["unchanged"]:
            st.markdown(f"- [{_passed_mark(r['passed'])}] {r['question']}")


VIEWS = {
    "Pass rate over time": view_pass_rate_over_time,
    "Per-question history": view_per_question_history,
    "Latest run detail": view_latest_run_detail,
    "Run-vs-run diff": view_run_vs_run_diff,
}


def main() -> None:
    st.set_page_config(page_title="Rubric Dashboard", layout="wide")
    st.title("Rubric Dashboard")

    if st.sidebar.button("Reload results"):
        load_all_runs.clear()

    runs = load_all_runs()
    if not runs:
        st.warning(
            "No runs found in `results/`. Run `python eval_harness.py` first, "
            "then click **Reload results** in the sidebar."
        )
        return

    choice = st.sidebar.radio("View", list(VIEWS.keys()))
    VIEWS[choice](runs)


if __name__ == "__main__":
    main()
