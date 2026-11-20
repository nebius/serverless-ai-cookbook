"""Public-source identity and reproducible selection checks; no paid inference."""
import csv
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vbench_data
spec = importlib.util.spec_from_file_location("video_with_vbench", ROOT / "src/generate.py")
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class VBenchDataTests(unittest.TestCase):
    def test_bundled_batch_has_25_sourced_prompts_per_category(self):
        source = vbench_data.verify(ROOT / "data/prompts.csv")
        rows = video.read_prompts(ROOT / "data/prompts.csv")
        self.assertEqual(len(rows), 200)
        self.assertEqual(source["per_category"], 25)
        self.assertEqual(Counter(row["category"] for row in rows),
                         {category: 25 for category in vbench_data.CATEGORIES})
        self.assertEqual(rows, source["selection"])
        self.assertEqual(len({row["id"] for row in rows}), 200)
        self.assertEqual(len({row["seed"] for row in rows}), 200)
        self.assertTrue(all(row["source_revision"] == source["revision"] for row in rows))

    def test_historical_eight_prompt_selection_remains_valid(self):
        source = vbench_data.verify(ROOT / "tests/fixtures/vbench-eight/input.csv")
        self.assertEqual(source["rows"], 8)
        self.assertEqual(source["per_category"], 1)
        self.assertEqual(len(video.read_prompts(ROOT / "tests/fixtures/vbench-eight/input.csv")), 8)

    def test_changed_csv_cannot_reuse_its_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prompts.csv"
            path.write_bytes((ROOT / "data/prompts.csv").read_bytes() + b"\n")
            path.with_suffix(".source.json").write_bytes((ROOT / "data/prompts.source.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "checksum"):
                vbench_data.verify(path)

    def test_selection_is_repeatable_and_larger_batches_have_distinct_ids(self):
        source = {"revision": "a" * 40, "files": {}}
        contents = {}
        for category in vbench_data.CATEGORIES:
            relative = f"prompts/prompts_per_category/{category}.txt"
            source["files"][relative] = {"rows": 100}
            contents[relative] = "\n".join(f"Original {category} prompt {n}" for n in range(100)).encode()
        first = vbench_data.select_rows(source, contents, 5, 42)
        self.assertEqual(first, vbench_data.select_rows(source, contents, 5, 42))
        self.assertEqual(len(first), 40)
        self.assertEqual(len({row["id"] for row in first}), 40)
        self.assertNotEqual(first, vbench_data.select_rows(source, contents, 5, 43))

    def test_invalid_selection_sizes_are_rejected(self):
        for size in [0, 101]:
            with self.assertRaises(ValueError):
                vbench_data.select_rows({}, {}, size, 42)

    def test_partial_or_mismatched_source_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("id,prompt,seed,category\nclip,Example,42,animal\n")
            with self.assertRaisesRegex(video.RecipeError, "columns"):
                video.read_prompts(path)
            with (ROOT / "data/prompts.csv").open() as original:
                rows = list(csv.DictReader(original))
            rows[0]["source_line"] = "999"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(video.RecipeError, "source metadata"):
                video.read_prompts(path)

    def test_csv_metadata_is_not_sent_as_generation_instructions(self):
        row = video.read_prompts(ROOT / "data/prompts.csv")[0]
        args = video.parser().parse_args([])
        fields = video.request_fields(row, args)
        self.assertEqual(fields["num_frames"], 49)
        self.assertEqual(fields["prompt"], row["prompt"])
        self.assertNotIn("category", fields)
        self.assertNotIn("source_revision", fields)

    def test_source_changes_reject_saved_clip_reuse(self):
        row = video.read_prompts(ROOT / "data/prompts.csv")[0]
        args = video.parser().parse_args([])
        fields = video.request_fields(row, args)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            changed = {**row, "source_line": row["source_line"] + 1}
            meta = {"input_row": changed, "fingerprint": video.fingerprint(fields)}
            video.atomic_json(output / (row["id"] + ".json"), meta)
            with self.assertRaisesRegex(video.RecipeError, "source metadata"):
                video.completed(output, row, fields)


if __name__ == "__main__":
    unittest.main()
