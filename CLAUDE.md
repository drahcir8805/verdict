1# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip install anthropic python-dotenv
# Copy .env.example to .env and paste your ANTHROPIC_API_KEY into it
python eval_harness.py
```

## Running

```bash
python eval_harness.py
```

No test suite yet. Manual verification is done by running the script end-to-end and checking the printed report.

## Architecture

Two files make up the system:

- **`eval_harness.py`** — all logic: loads the dataset, calls the model twice per question (once to answer, once to judge), prints a pass/fail report.
- **`dataset.json`** — the golden dataset: a list of `{ "question", "criteria" }` objects. This is the only file that changes when adding or modifying eval cases.

### Core loop (in `run_eval`)

1. Load `dataset.json` via `load_dataset()`
2. For each item: call `get_answer()` → call `judge_answer()` → collect result
3. Print summary report

### LLM-as-judge pattern

`judge_answer()` sends the original question, the model's answer, and the criteria to the same model and asks it to respond with `PASS` or `FAIL - <reason>`. The verdict is parsed by checking if the response starts with `PASS`.

## Planned next steps (from README)

In order: async eval queue → result persistence → compare mode → Postgres + pgvector → dashboard → GitHub PR integration.
