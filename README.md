# Rubric

A lightweight eval harness for LLM-powered features — catches quality regressions before they ship, not after customers notice.

## The problem

Once an AI feature ships, teams keep changing it: swapping to a cheaper model, tweaking a prompt, adjusting context length. Each change is a gamble. We ask did quality get better, worse, or stay the same? Most teams find out from angry users. Rubric answers that question automatically, before the change reaches production.

## How it works

1. **A golden dataset** — a fixed set of questions with known-good criteria, the "quiz" every version has to pass. Each question can be tagged (`code`, `hedging`, `reasoning`, etc.) so a regression report tells you *what kind* of quality dropped.
2. **Ask** — the model answers each question like a normal user would.
3. **Judge** — a second, *different* model call grades that answer against the criteria (pass/fail + reasoning). This is "LLM-as-judge": necessary because AI answers are open-ended text, not multiple choice. We use Haiku for answers and Sonnet as the judge so the model isn't marking its own homework.
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
python eval_harness.py --meta-eval                    # score the judge against judge_labels.json
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

Five views in the sidebar:

- **Pass rate over time** — line chart across all runs, plus a summary table.
- **Category trends** — one line per tag, so you can see (for example) `hedging` quality drop while `algorithms` stays flat.
- **Per-question history** — pick a question, see how it's fared run-by-run (useful for spotting flakes).
- **Latest run detail** — the most recent run's per-category rollup plus per-question verdicts and full answers.
- **Run-vs-run diff** — pick any two runs, get the same regressions/improvements/unchanged split as `--compare`.

Click **Reload results** in the sidebar after a new eval run to refresh the cache.

## Judge meta-eval

The judge is an LLM too — sometimes lenient, sometimes strict, sometimes making up requirements that aren't in the criteria. `judge_labels.json` is a small human-labeled ground-truth file used to measure how often the judge is actually right.

Schema per entry:

```json
{
  "question": "…the original question…",
  "answer": "…the answer the model gave…",
  "judge_passed": true,
  "judge_reason": "PASS - correct year",
  "human_passed": true,
  "notes": "why you agree / disagree with the judge"
}
```

Run it:

```bash
python eval_harness.py --meta-eval
```

You get an agreement rate plus a breakdown of **false positives** (judge said PASS but the answer really was bad) and **false negatives** (judge FAILed a good answer). To grow the labeled set, hand-label real triples from `results/*.json` after each eval and append them to `judge_labels.json` — the more entries, the more trustworthy the judge accuracy number.

The bundled file ships with 5 seed entries to demo the tooling; replace them with real labels as your dataset grows.

## Repo layout

```
eval_harness.py          # ask, judge, compare, meta-eval, markdown output — all logic
dashboard.py             # local Streamlit dashboard over results/*.json
dataset.json             # the golden questions + criteria + optional tags
judge_labels.json        # human ground truth for judge meta-eval
requirements.txt         # anthropic, python-dotenv, streamlit
.env.example             # template — copy to .env locally
.github/workflows/eval.yml   # runs on PR + push to main
results/                 # timestamped run outputs (gitignored)
```

## Tech stack

**Now:** Python, Anthropic API, GitHub Actions.

**Next up (in order of leverage):**
1. **Restore CI + delete demo data** — flip `.github/workflows/eval.yml` back to `pull_request` / `push: [main]` when API credits are restored, delete the synthetic `results/*.json` seed files, and open a throwaway PR to confirm the full loop (cross-model judge → per-category rollup → sticky PR comment) still works end-to-end. Everything below is theoretical until this happens.
2. **Cost + latency per question** — record `input_tokens`, `output_tokens`, and `duration_ms` on each result, roll them up per run, add a cost-trend line to the dashboard. Small change, unlocks cost-regression detection alongside quality-regression detection.
3. **Grow `judge_labels.json`** — the tooling is in; the ground-truth set needs to grow from 5 seeds to ~30-50 real triples before the meta-eval agreement number is statistically meaningful. Slow-burn manual chore; hand-label real disagreements as they come out of live runs.
4. **Persistence: SQLite** — replace `results/*.json` with a single `results.db`. Not urgent until run count is ~50+ and the dashboard's file scan starts to hurt. Postgres later if / when a hosted dashboard is worth it.
5. **Judge prompt v2** — add few-shot examples or chain-of-thought to the judge prompt to lift agreement rate. Premature without more labels (#3) to measure the effect against.