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

## PR integration

`.github/workflows/eval.yml` runs the eval on every PR and posts a sticky comment with the results. On pushes to `main`, the run's result JSON is stored as an artifact named `eval-baseline`; subsequent PRs download it and produce a proper diff (regressions, improvements, unchanged).

**One-time setup:** add `ANTHROPIC_API_KEY` under the repo's *Settings → Secrets and variables → Actions*.

The first PR after enabling CI will post a standalone summary (no baseline yet). After the next merge to `main`, subsequent PRs get the diff view.

## Example output

```
[1/5] Asking: What is the time complexity of binary search?
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

## Tech stack

**Now:** Python, Anthropic API

**Planned:** Postgres + pgvector, a small dashboard