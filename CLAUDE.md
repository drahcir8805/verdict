1# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip install -r requirements.txt
# Copy .env.example to .env and paste your ANTHROPIC_API_KEY into it
python eval_harness.py
```

## Running

```bash
python eval_harness.py                             # run eval, save JSON result
python eval_harness.py --markdown-out summary.md   # also write PR-comment markdown
python eval_harness.py --compare A B               # diff two runs (stdout)
python eval_harness.py --compare A B --markdown-out summary.md  # diff → markdown
python eval_harness.py --compare                   # diff latest two runs in results/
streamlit run dashboard.py                         # local dashboard over results/*.json
```

No test suite yet. Manual verification is done by running the script end-to-end and checking the printed report.

## Architecture

- **`eval_harness.py`** — loads the dataset, runs answer+judge in parallel, saves JSON to `results/`, prints a pass/fail report. Also handles compare-mode and markdown output.
- **`dataset.json`** — the golden dataset: a list of `{ "question", "criteria" }` objects. This is the only file that changes when adding or modifying eval cases.
- **`dashboard.py`** — Streamlit app that reads `results/*.json` and renders four views (pass rate over time, per-question history, latest run detail, run-vs-run diff). Reuses `compute_diff()` from `eval_harness.py` for the diff view.
- **`.github/workflows/eval.yml`** — runs the eval on PRs and pushes to main. On PR, downloads the most recent `eval-baseline` artifact from main and posts a sticky diff comment. On push to main, uploads the fresh run as the new `eval-baseline`.

### Core loop (in `run_eval`)

1. Load `dataset.json` via `load_dataset()`
2. `asyncio.gather` over `eval_one(item)`: `get_answer()` → `judge_answer()`
3. `save_results()` to `results/<timestamp>.json`
4. Optional `format_run_markdown()` for PR comments

### LLM-as-judge pattern

`judge_answer()` sends the original question, the model's answer, and the criteria to a **different** model (see `JUDGE_MODEL`) and asks it to respond with `PASS` or `FAIL - <reason>`. The verdict is parsed by checking if the response starts with `PASS`. `ANSWER_MODEL` and `JUDGE_MODEL` are separate constants at the top of `eval_harness.py`; both are recorded in every saved run under `model` and `judge_model` respectively.

### Diff pattern

`compute_diff(before, after)` is a pure function returning `{regressions, improvements, unchanged, delta}`. Two formatters consume it: `format_diff_markdown()` for PR comments, and inline prints inside `compare()` for CLI use.

## Planned next steps

Postgres + pgvector for run history, then a small dashboard. Both premature until dataset size or query patterns actually demand them.
