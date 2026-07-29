"""
Sanity tests for eval_harness — no API calls, no cost.

Covers the pure functions and I/O helpers so structural bugs (bad JSON, wrong
diff math, malformed markdown) are caught in CI without spending tokens.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import eval_harness as eh


def _make_run(
    pass_map: dict[str, bool],
    model: str = "test-answer-model",
    judge_model: str | None = "test-judge-model",
    tags_map: dict[str, list[str]] | None = None,
) -> dict:
    """Build a saved-run payload from {question: passed}."""
    tags_map = tags_map or {}
    results = [
        {
            "question": q,
            "tags": tags_map.get(q, []),
            "answer": f"answer to {q}",
            "passed": passed,
            "reason": "PASS" if passed else "FAIL - wrong",
        }
        for q, passed in pass_map.items()
    ]
    passed_count = sum(pass_map.values())
    total = len(pass_map)
    payload = {
        "timestamp": "2026-01-01T00-00-00",
        "model": model,
        "passed": passed_count,
        "total": total,
        "pass_rate": passed_count / total if total else 0.0,
        "results": results,
    }
    if judge_model is not None:
        payload["judge_model"] = judge_model
    return payload


class LoadDatasetTests(unittest.TestCase):
    def test_loads_written_file(self):
        data = [{"question": "q1", "criteria": "c1"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        try:
            self.assertEqual(eh.load_dataset(path), data)
        finally:
            path.unlink()

    def test_real_dataset_schema(self):
        """Every entry in the shipped dataset.json must have question + criteria."""
        dataset = eh.load_dataset(eh.DATASET_PATH)
        self.assertGreater(len(dataset), 0)
        for item in dataset:
            self.assertIn("question", item)
            self.assertIn("criteria", item)
            self.assertIsInstance(item["question"], str)
            self.assertIsInstance(item["criteria"], str)
            if "tags" in item:
                self.assertIsInstance(item["tags"], list)
                for tag in item["tags"]:
                    self.assertIsInstance(tag, str)
                    self.assertTrue(tag, "tags must be non-empty strings")


class ComputeDiffTests(unittest.TestCase):
    def test_classifies_regression_improvement_unchanged(self):
        before = _make_run({"a": True, "b": False, "c": True, "d": False})
        after = _make_run({"a": False, "b": True, "c": True, "d": False})
        diff = eh.compute_diff(before, after)
        self.assertEqual([r["question"] for r in diff["regressions"]], ["a"])
        self.assertEqual([r["question"] for r in diff["improvements"]], ["b"])
        self.assertEqual(
            sorted(r["question"] for r in diff["unchanged"]), ["c", "d"]
        )

    def test_delta_matches_pass_rate_difference(self):
        before = _make_run({"a": True, "b": False})  # 50%
        after = _make_run({"a": True, "b": True})    # 100%
        diff = eh.compute_diff(before, after)
        self.assertAlmostEqual(diff["delta"], 0.5)

    def test_questions_only_in_after_are_ignored(self):
        before = _make_run({"a": True})
        after = _make_run({"a": True, "new": False})
        diff = eh.compute_diff(before, after)
        all_qs = [r["question"] for r in diff["regressions"]
                  + diff["improvements"] + diff["unchanged"]]
        self.assertNotIn("new", all_qs)


class CategoryStatsTests(unittest.TestCase):
    def test_groups_by_tag(self):
        run = _make_run(
            {"a": True, "b": False, "c": True, "d": True},
            tags_map={"a": ["code"], "b": ["code"], "c": ["hedging"], "d": ["hedging"]},
        )
        stats = eh.compute_category_stats(run["results"])
        self.assertEqual(stats["code"], {"passed": 1, "total": 2, "pass_rate": 0.5})
        self.assertEqual(stats["hedging"], {"passed": 2, "total": 2, "pass_rate": 1.0})

    def test_untagged_questions_bucketed_separately(self):
        run = _make_run({"a": True, "b": False}, tags_map={"a": ["code"]})
        stats = eh.compute_category_stats(run["results"])
        self.assertIn("code", stats)
        self.assertIn("(untagged)", stats)
        self.assertEqual(stats["(untagged)"]["total"], 1)

    def test_multi_tag_question_counted_once_per_tag(self):
        run = _make_run({"a": False}, tags_map={"a": ["code", "hedging"]})
        stats = eh.compute_category_stats(run["results"])
        self.assertEqual(stats["code"]["total"], 1)
        self.assertEqual(stats["hedging"]["total"], 1)
        self.assertEqual(stats["code"]["passed"], 0)


class MarkdownFormatterTests(unittest.TestCase):
    def test_run_markdown_contains_headline_stats(self):
        payload = _make_run(
            {"a": True, "b": False}, model="claude-test", judge_model="claude-judge"
        )
        md = eh.format_run_markdown(payload)
        self.assertIn("Rubric Eval Results", md)
        self.assertIn("1/2 passed", md)
        self.assertIn("50%", md)
        self.assertIn("claude-test", md)
        self.assertIn("claude-judge", md)
        self.assertIn("[FAIL]", md)
        self.assertIn("[PASS]", md)

    def test_run_markdown_omits_judge_when_same_as_answer(self):
        payload = _make_run({"a": True}, model="same", judge_model="same")
        md = eh.format_run_markdown(payload)
        self.assertIn("`same`", md)
        self.assertNotIn("judged", md)

    def test_run_markdown_handles_legacy_payload_without_judge(self):
        payload = _make_run({"a": True}, model="legacy", judge_model=None)
        md = eh.format_run_markdown(payload)
        self.assertIn("legacy", md)

    def test_run_markdown_includes_category_table_when_tags_present(self):
        payload = _make_run(
            {"a": True, "b": False},
            tags_map={"a": ["code"], "b": ["hedging"]},
        )
        md = eh.format_run_markdown(payload)
        self.assertIn("By category", md)
        self.assertIn("`code`", md)
        self.assertIn("`hedging`", md)

    def test_diff_markdown_includes_category_delta_when_tags_present(self):
        before = _make_run(
            {"a": True, "b": False},
            tags_map={"a": ["code"], "b": ["code"]},
        )
        after = _make_run(
            {"a": True, "b": True},
            tags_map={"a": ["code"], "b": ["code"]},
        )
        md = eh.format_diff_markdown(eh.compute_diff(before, after), "b.json", "a.json")
        self.assertIn("By category", md)
        self.assertIn("`code`", md)
        self.assertIn("+50%", md)

    def test_diff_markdown_shows_positive_delta(self):
        before = _make_run({"a": False})
        after = _make_run({"a": True})
        md = eh.format_diff_markdown(eh.compute_diff(before, after), "b.json", "a.json")
        self.assertIn("+100%", md)
        self.assertIn("Improvements (1)", md)
        self.assertIn("Regressions (0)", md)

    def test_diff_markdown_shows_negative_delta(self):
        before = _make_run({"a": True})
        after = _make_run({"a": False})
        md = eh.format_diff_markdown(eh.compute_diff(before, after), "b.json", "a.json")
        self.assertIn("-100%", md)
        self.assertIn("Regressions (1)", md)
        self.assertIn("Improvements (0)", md)


class SaveResultsTests(unittest.TestCase):
    def test_writes_file_with_expected_schema(self):
        original_dir = eh.RESULTS_DIR
        with tempfile.TemporaryDirectory() as tmp:
            eh.RESULTS_DIR = Path(tmp)
            try:
                results = [
                    {"question": "q", "answer": "a", "passed": True, "reason": "PASS"}
                ]
                path = eh.save_results(results, passed_count=1)
                self.assertTrue(path.exists())
                payload = json.loads(path.read_text())
                self.assertEqual(payload["passed"], 1)
                self.assertEqual(payload["total"], 1)
                self.assertEqual(payload["pass_rate"], 1.0)
                self.assertEqual(payload["model"], eh.ANSWER_MODEL)
                self.assertEqual(payload["judge_model"], eh.JUDGE_MODEL)
                self.assertNotEqual(
                    eh.ANSWER_MODEL,
                    eh.JUDGE_MODEL,
                    "cross-model judge should differ from answer model",
                )
                self.assertEqual(payload["results"], results)
            finally:
                eh.RESULTS_DIR = original_dir


if __name__ == "__main__":
    unittest.main()
