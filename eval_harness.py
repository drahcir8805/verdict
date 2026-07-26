"""
Eval Harness — Version Zero
============================
The smallest possible version of an LLM eval harness. This is Step 1
of a bigger project — no parallel processing, no database, no GitHub
integration yet. Just the core idea:

    "Can a second AI call tell us if the first AI call did a good job?"

Once this works, we add the fancier pieces one at a time.

SETUP (do this before running):
1. Get a free API key at https://console.anthropic.com
2. Set it as an environment variable in your terminal:
     Mac/Linux:   export ANTHROPIC_API_KEY="your-key-here"
     Windows:     setx ANTHROPIC_API_KEY "your-key-here"
3. Install the SDK:
     pip install anthropic
4. Run it:
     python eval_harness.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from anthropic import AsyncAnthropic

client = AsyncAnthropic()

MODEL = "claude-haiku-4-5-20251001"

DATASET_PATH = Path(__file__).parent / "dataset.json"


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


async def get_answer(question: str) -> str:
    response = await client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


async def judge_answer(question: str, answer: str, criteria: str) -> dict:
    judge_prompt = f"""You are grading an AI's answer to a question.

Question: {question}
Criteria for a good answer: {criteria}
The AI's answer: {answer}

Does this answer meet the criteria? Respond with EXACTLY one line in this format:
PASS or FAIL - <one sentence reason>"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    verdict_text = response.content[0].text.strip()
    passed = verdict_text.upper().startswith("PASS")
    return {"passed": passed, "reason": verdict_text}


async def eval_one(item: dict) -> dict:
    """Runs a single question end-to-end: ask then judge."""
    answer = await get_answer(item["question"])
    verdict = await judge_answer(item["question"], answer, item["criteria"])
    return {"question": item["question"], "answer": answer, **verdict}


async def run_eval():
    dataset = load_dataset(DATASET_PATH)
    print(f"Running {len(dataset)} questions in parallel...\n")

    results = await asyncio.gather(*[eval_one(item) for item in dataset])

    for i, result in enumerate(results, start=1):
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{i}/{len(dataset)}] {result['question']}")
        print(f"  -> Answer: {result['answer'][:100]}{'...' if len(result['answer']) > 100 else ''}")
        print(f"  -> Judge says: {status} ({result['reason']})")

    passed_count = sum(1 for r in results if r["passed"])
    total = len(results)
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed_count}/{total} passed ({passed_count / total:.0%})")
    print("=" * 50)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['question']}")


if __name__ == "__main__":
    asyncio.run(run_eval())
