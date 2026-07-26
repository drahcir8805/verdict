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

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from anthropic import AsyncAnthropic

client = AsyncAnthropic()

MODEL = "claude-haiku-4-5-20251001"

DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


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


def save_results(results: list[dict], passed_count: int) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    path = RESULTS_DIR / f"{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "model": MODEL,
        "passed": passed_count,
        "total": len(results),
        "pass_rate": passed_count / len(results),
        "results": results,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


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

    path = save_results(results, passed_count)
    print(f"\nResults saved to {path}")


def find_latest_two() -> tuple[Path, Path]:
    if not RESULTS_DIR.exists():
        print("No results yet. Run the eval first.")
        sys.exit(1)
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) < 2:
        print("Need at least 2 runs to compare. Run the eval again to get a second result.")
        sys.exit(1)
    return files[-2], files[-1]


def compare(before_path: Path, after_path: Path):
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    print(f"Comparing runs:")
    print(f"  BEFORE: {before_path.name}  (model: {before['model']}, pass rate: {before['pass_rate']:.0%})")
    print(f"  AFTER:  {after_path.name}  (model: {after['model']}, pass rate: {after['pass_rate']:.0%})")

    before_by_q = {r["question"]: r for r in before["results"]}
    after_by_q = {r["question"]: r for r in after["results"]}

    regressions, improvements, unchanged = [], [], []

    for question, after_result in after_by_q.items():
        before_result = before_by_q.get(question)
        if before_result is None:
            continue
        if before_result["passed"] and not after_result["passed"]:
            regressions.append(after_result)
        elif not before_result["passed"] and after_result["passed"]:
            improvements.append(after_result)
        else:
            unchanged.append(after_result)

    delta = after["pass_rate"] - before["pass_rate"]
    delta_str = f"+{delta:.0%}" if delta > 0 else f"{delta:.0%}"
    print(f"\nPass rate: {before['pass_rate']:.0%} → {after['pass_rate']:.0%} ({delta_str})")

    print(f"\nREGRESSIONS ({len(regressions)}):")
    if regressions:
        for r in regressions:
            print(f"  [PASS→FAIL] {r['question']}")
            print(f"    Reason: {r['reason']}")
    else:
        print("  none")

    print(f"\nIMPROVEMENTS ({len(improvements)}):")
    if improvements:
        for r in improvements:
            print(f"  [FAIL→PASS] {r['question']}")
    else:
        print("  none")

    print(f"\nUNCHANGED ({len(unchanged)}):")
    for r in unchanged:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['question']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM eval harness")
    parser.add_argument(
        "--compare",
        nargs="*",
        metavar="FILE",
        help="Compare two runs. Pass two file paths, or omit to compare the latest two.",
    )
    args = parser.parse_args()

    if args.compare is not None:
        if len(args.compare) == 2:
            compare(Path(args.compare[0]), Path(args.compare[1]))
        elif len(args.compare) == 0:
            before, after = find_latest_two()
            compare(before, after)
        else:
            print("Pass exactly 0 or 2 files to --compare.")
            sys.exit(1)
    else:
        asyncio.run(run_eval())
