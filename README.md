# Rubric

A lightweight eval harness for LLM-powered features — catches quality regressions before they ship, not after customers notice.

## The problem

Once an AI feature ships, teams keep changing it: swapping to a cheaper model, tweaking a prompt, adjusting context length. Each change is a gamble. We ask did quality get better, worse, or stay the same? Most teams find out from angry users. Rubric answers that question automatically, before the change reaches production.

## How it works

1. **A golden dataset** — a fixed set of questions with known-good criteria, the "quiz" every version has to pass.
2. **Ask** — the model answers each question like a normal user would.
3. **Judge** — a second model call grades that answer against the criteria (pass/fail + reasoning). This is "LLM-as-judge": necessary because AI answers are open-ended text, not multiple choice.
4. **Report** — pass rate across the whole dataset, with per-question reasoning for every failure.

## Status: v0.1

CLI script + GitHub Action. Every PR gets a comment showing pass rate and any regressions against `main`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then paste your key from console.anthropic.com
python eval_harness.py
```

The script reads `ANTHROPIC_API_KEY` from `.env` at startup. `.env` is gitignored — never commit it.

## Commands

```bash
python eval_harness.py                                # run eval, save results/<timestamp>.json
python eval_harness.py --markdown-out summary.md      # also write a PR-comment-ready summary
python eval_harness.py --compare A.json B.json        # diff two runs (regressions / improvements)
python eval_harness.py --compare                      # diff the latest two runs in results/
python eval_harness.py --compare A B --markdown-out summary.md   # diff -> markdown
streamlit run dashboard.py                            # local dashboard over results/*.json
```

Each run appends a timestamped JSON under `results/` with the model, pass rate, and per-question verdicts.

## Example output

```
[1/5] What is the time complexity of binary search?
  -> Answer: The time complexity of binary search is O(log n)...
  -> Judge says: PASS (Correctly states O(log n) with explanation)

==================================================
RESULTS: 4/5 passed (80%)
==================================================
[PASS] What is the time complexity of binary search?
[PASS] Explain what a REST API is in 2 sentences.
[FAIL] What does 'CI/CD' stand for and why does it matter?
[PASS] What's the difference between SQL and NoSQL databases?
[PASS] What is a race condition in concurrent programming?
```

## PR integration

`.github/workflows/eval.yml` runs the eval on every PR and posts a sticky comment with the results. On pushes to `main`, the run's result JSON is stored as an artifact named `eval-baseline`; subsequent PRs download it and produce a proper diff (regressions, improvements, unchanged).

**One-time setup:** add `ANTHROPIC_API_KEY` under the repo's *Settings → Secrets and variables → Actions*.

The first PR after enabling CI will post a standalone summary (no baseline yet). After the next merge to `main`, subsequent PRs get the diff view.

### Sample PR comment

> **Pass rate:** 80% → 60% (**−20%**)
>
> **Regressions (1)**
> - **What does 'CI/CD' stand for?** — `FAIL - omitted the acronym expansion`
>
> **Improvements (0)** — _none_
>
> <details><summary>Unchanged (3)</summary>[PASS] Big-O of binary search? · [PASS] Explain REST · [PASS] SQL vs NoSQL</details>

## Dashboard

A local Streamlit app that reads `results/*.json` — no database, no server, no deploy.

```bash
streamlit run dashboard.py    # opens http://localhost:8501
```

Four views in the sidebar:

- **Pass rate over time** — line chart across all runs, plus a summary table.
- **Per-question history** — pick a question, see how it's fared run-by-run (useful for spotting flakes).
- **Latest run detail** — the most recent run's per-question verdicts and full answers.
- **Run-vs-run diff** — pick any two runs, get the same regressions/improvements/unchanged split as `--compare`.

Click **Reload results** in the sidebar after a new eval run to refresh the cache.

## Repo layout

```
eval_harness.py          # ask, judge, compare, markdown output — all logic
dashboard.py             # local Streamlit dashboard over results/*.json
dataset.json             # the golden questions + criteria (edit this to add cases)
requirements.txt         # anthropic, python-dotenv, streamlit
.env.example             # template — copy to .env locally
.github/workflows/eval.yml   # runs on PR + push to main
results/                 # timestamped run outputs (gitignored)
```

## Tech stack

**Now:** Python, Anthropic API, GitHub Actions.

**Next up (in order of leverage):**
1. **Cross-model judge** — let a stronger model grade a cheaper model's answers so the judge isn't marking its own homework.
2. **Judge meta-eval** — a small human-labeled slice so we can measure how often the judge is right, not just how often the model passes.
3. **Grow the dataset** — 20-50 questions, tagged by category, so a regression report can pinpoint *what kind* of quality dropped.
4. **Persistence + dashboard** — Postgres and a UI, once run history is big enough that JSON files start hurting.