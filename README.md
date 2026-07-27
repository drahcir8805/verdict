# Rubric

A lightweight eval harness for LLM-powered features — catches quality regressions before they ship, not after customers notice.

## The problem

Once an AI feature ships, teams keep changing it: swapping to a cheaper model, tweaking a prompt, adjusting context length. Each change is a gamble. We ask did quality get better, worse, or stay the same? Most teams find out from angry users. Rubric answers that question automatically, before the change reaches production.

## How it works

1. **A golden dataset** — a fixed set of questions with known-good criteria, the "quiz" every version has to pass.
2. **Ask** — the model answers each question like a normal user would.
3. **Judge** — a second model call grades that answer against the criteria (pass/fail + reasoning). This is "LLM-as-judge": necessary because AI answers are open-ended text, not multiple choice.
4. **Report** — pass rate across the whole dataset, with per-question reasoning for every failure.

## Status: v0

Currently a single-threaded CLI script that runs the loop above end to end. This is the foundation the rest of the system builds on.

## Setup

```bash
pip install anthropic python-dotenv
cp .env.example .env      # then paste your key from console.anthropic.com
python eval_harness.py
```

The script reads `ANTHROPIC_API_KEY` from `.env` at startup. `.env` is gitignored — never commit it.

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

**Planned:** async eval queue, Postgres + pgvector, a small dashboard, GitHub PR integration