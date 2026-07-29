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
2. Copy .env.example to .env and paste your key into it:
     ANTHROPIC_API_KEY=sk-ant-...
3. Install dependencies:
     pip install anthropic python-dotenv
4. Run it:
     python eval_harness.py
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from anthropic import AsyncAnthropic

client = AsyncAnthropic()

ANSWER_MODEL = "claude-haiku-4-5-20251001"
JUDGE_MODEL = "claude-sonnet-4-6"

DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


async def get_answer(question: str) -> str:
    response = await client.messages.create(
        model=ANSWER_MODEL,
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
        model=JUDGE_MODEL,
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
        "model": ANSWER_MODEL,
        "judge_model": JUDGE_MODEL,
        "passed": passed_count,
        "total": len(results),
        "pass_rate": passed_count / len(results),
        "results": results,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def compute_diff(before: dict, after: dict) -> dict:
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

    return {
        "before": before,
        "after": after,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "delta": after["pass_rate"] - before["pass_rate"],
    }


def _model_line(payload: dict) -> str:
    answer = payload.get("model", "?")
    judge = payload.get("judge_model")
    if judge and judge != answer:
        return f"`{answer}` answered · `{judge}` judged"
    return f"`{answer}`"


def format_run_markdown(payload: dict) -> str:
    lines = [
        "## Rubric Eval Results",
        "",
        f"**{payload['passed']}/{payload['total']} passed ({payload['pass_rate']:.0%})** — {_model_line(payload)}",
        "",
        "<details>",
        "<summary>Per-question results</summary>",
        "",
    ]
    for r in payload["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- **[{status}]** {r['question']}")
        if not r["passed"]:
            lines.append(f"  - `{r['reason']}`")
    lines += [
        "",
        "</details>",
        "",
        "<sub>No baseline from main yet — a regression diff will appear once main has a completed run.</sub>",
        "",
    ]
    return "\n".join(lines)


def format_diff_markdown(diff: dict, before_name: str, after_name: str) -> str:
    before, after, delta = diff["before"], diff["after"], diff["delta"]
    if delta > 0:
        delta_str = f"**+{delta:.0%}**"
    elif delta < 0:
        delta_str = f"**{delta:.0%}**"
    else:
        delta_str = "no change"

    lines = [
        "## Rubric Eval Results",
        "",
        f"**Pass rate:** {before['pass_rate']:.0%} → {after['pass_rate']:.0%} ({delta_str})",
        "",
        f"Baseline `{before_name}` ({before['total']} qs) → Current `{after_name}` ({after['total']} qs) · {_model_line(after)}",
        "",
        f"### Regressions ({len(diff['regressions'])})",
    ]
    if diff["regressions"]:
        for r in diff["regressions"]:
            lines.append(f"- **{r['question']}**")
            lines.append(f"  - `{r['reason']}`")
    else:
        lines.append("_none_")
    lines += ["", f"### Improvements ({len(diff['improvements'])})"]
    if diff["improvements"]:
        for r in diff["improvements"]:
            lines.append(f"- {r['question']}")
    else:
        lines.append("_none_")
    lines += [
        "",
        "<details>",
        f"<summary>Unchanged ({len(diff['unchanged'])})</summary>",
        "",
    ]
    for r in diff["unchanged"]:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- **[{status}]** {r['question']}")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


async def run_eval(markdown_out: Path | None = None) -> Path:
    dataset = load_dataset(DATASET_PATH)
    print(
        f"Running {len(dataset)} questions in parallel — "
        f"answers by {ANSWER_MODEL}, judged by {JUDGE_MODEL}\n"
    )

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

    if markdown_out is not None:
        with open(path) as f:
            payload = json.load(f)
        markdown_out.write_text(format_run_markdown(payload), encoding="utf-8")
        print(f"Markdown summary written to {markdown_out}")

    return path


def find_latest_two() -> tuple[Path, Path]:
    if not RESULTS_DIR.exists():
        print("No results yet. Run the eval first.")
        sys.exit(1)
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) < 2:
        print("Need at least 2 runs to compare. Run the eval again to get a second result.")
        sys.exit(1)
    return files[-2], files[-1]


def compare(before_path: Path, after_path: Path, markdown_out: Path | None = None):
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    diff = compute_diff(before, after)

    def _describe(run: dict) -> str:
        parts = [f"answer={run.get('model', '?')}"]
        judge = run.get("judge_model")
        if judge and judge != run.get("model"):
            parts.append(f"judge={judge}")
        parts.append(f"pass rate: {run['pass_rate']:.0%}")
        return ", ".join(parts)

    print(f"Comparing runs:")
    print(f"  BEFORE: {before_path.name}  ({_describe(before)})")
    print(f"  AFTER:  {after_path.name}  ({_describe(after)})")

    delta = diff["delta"]
    delta_str = f"+{delta:.0%}" if delta > 0 else f"{delta:.0%}"
    print(f"\nPass rate: {before['pass_rate']:.0%} -> {after['pass_rate']:.0%} ({delta_str})")

    print(f"\nREGRESSIONS ({len(diff['regressions'])}):")
    if diff["regressions"]:
        for r in diff["regressions"]:
            print(f"  [PASS->FAIL] {r['question']}")
            print(f"    Reason: {r['reason']}")
    else:
        print("  none")

    print(f"\nIMPROVEMENTS ({len(diff['improvements'])}):")
    if diff["improvements"]:
        for r in diff["improvements"]:
            print(f"  [FAIL->PASS] {r['question']}")
    else:
        print("  none")

    print(f"\nUNCHANGED ({len(diff['unchanged'])}):")
    for r in diff["unchanged"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['question']}")

    if markdown_out is not None:
        markdown_out.write_text(
            format_diff_markdown(diff, before_path.name, after_path.name),
            encoding="utf-8",
        )
        print(f"\nMarkdown summary written to {markdown_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM eval harness")
    parser.add_argument(
        "--compare",
        nargs="*",
        metavar="FILE",
        help="Compare two runs. Pass two file paths, or omit to compare the latest two.",
    )
    parser.add_argument(
        "--markdown-out",
        metavar="PATH",
        type=Path,
        help="Write a markdown summary (for a PR comment) to this path.",
    )
    args = parser.parse_args()

    if args.compare is not None:
        if len(args.compare) == 2:
            compare(Path(args.compare[0]), Path(args.compare[1]), args.markdown_out)
        elif len(args.compare) == 0:
            before, after = find_latest_two()
            compare(before, after, args.markdown_out)
        else:
            print("Pass exactly 0 or 2 files to --compare.")
            sys.exit(1)
    else:
        asyncio.run(run_eval(args.markdown_out))
