"""Offline checks for distinct input passages, provenance and portable output."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from data import _chunk_count, _select, load_documents, manifest_digest, prepare


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


class PassageDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundled = self.root / "bundled"
        self.bundled.mkdir()
        self.output, self.cache = self.root / "output", self.root / "cache"
        self.license = b"Fixture license only; not production data.\n"
        self.card = b"---\nlicense: cc-by-sa-3.0\n---\nFixture card.\n"
        self.attribution = b"Fixture source attribution.\n"
        for filename, raw in [("LICENSE", self.license), ("DATASET_CARD.md", self.card), ("SOURCE.md", self.attribution)]:
            (self.bundled / filename).write_bytes(raw)
        self.rows = [
            {"instruction": "Excluded empty", "context": "", "response": "not an input", "category": "open_qa"},
            {"instruction": "First passage", "context": "alpha beta gamma delta epsilon zeta eta theta", "response": "never indexed", "category": "closed_qa"},
            {"instruction": "Duplicate spacing", "context": "alpha  beta gamma\n delta epsilon zeta eta theta", "category": "closed_qa"},
            {"instruction": "Too short", "context": "one two", "category": "closed_qa"},
            {"instruction": "Second passage", "context": "red orange yellow green blue indigo violet black white café", "response": "never indexed either", "category": "summarization"},
            {"instruction": "After the limit", "context": "another real source passage is not selected after the limit", "category": "closed_qa"},
        ]
        self.raw = b"".join(json_bytes(row) for row in self.rows)
        self.source = {"schema": 1, "dataset": "fixture only", "revision": "fixture",
                       "selection": {"field": "context", "minimum_words": 8, "count": 2,
                                     "deduplication": "SHA256 of collapsed whitespace; keep first in source order"},
                       "source": {"url": "https://example.org/pinned.jsonl", "view_url": "https://example.org/blob/pinned.jsonl",
                                  "sha256": digest(self.raw), "bytes": len(self.raw),
                                  "card_url": "https://example.org/README.md", "card_sha256": digest(self.card)},
                       "license": {"name": "fixture only", "url": "https://example.org/license", "sha256": digest(self.license)},
                       "attribution_sha256": digest(self.attribution)}
        metadata = []
        for line_number in (2, 5):
            row, line = self.rows[line_number - 1], self.raw.decode().splitlines()[line_number - 1]
            text = row["context"]
            metadata.append({"id": f"dolly-context-L{line_number:05d}", "title": row["instruction"],
                             "source_url": self.source["source"]["view_url"] + f"#L{line_number}",
                             "source_line": line_number, "record_sha256": digest(line.encode()),
                             "text_sha256": digest(text.encode()), "normalized_text_sha256": digest(" ".join(text.split()).encode()),
                             "category": row["category"], "words": len(text.split()), "bytes": len(text.encode())})
        self.source["documents"] = metadata
        self.source_path = self.bundled / "source.json"
        self.save_source()

    def save_source(self):
        self.source_path.write_bytes(json_bytes(self.source))

    def prepare(self, fetch=None):
        return prepare(self.output, self.cache, source_path=self.source_path, fetch=fetch or (lambda url: self.raw))

    def test_first_distinct_substantial_contexts_only_and_exact_text_preserved(self):
        manifest = self.prepare()
        docs = load_documents(self.output)
        self.assertEqual([d["id"] for d in docs], ["dolly-context-L00002", "dolly-context-L00005"])
        self.assertEqual([d["text"] for d in docs], [self.rows[1]["context"], self.rows[4]["context"]])
        self.assertEqual(manifest["totals"], {"documents": 2, "words": 18, "text_bytes": 105, "chunks_160_words": 2})
        self.assertNotIn("never indexed", (self.output / "documents.jsonl").read_text())
        self.assertEqual({p.name for p in self.output.iterdir()}, {"documents.jsonl", "manifest.json", "LICENSE", "SOURCE.md"})
        self.assertEqual((self.output / "LICENSE").read_bytes(), self.license)

    def test_cached_rerun_is_byte_identical_and_does_not_download(self):
        first = self.prepare()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        second = self.prepare(lambda url: self.fail("Verified source must be cached"))
        self.assertEqual(first, second)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        self.assertEqual(manifest_digest(self.output), digest(before["manifest.json"]))
        self.assertEqual(load_documents(self.output / "documents.jsonl"), load_documents(self.output))

    def test_wrong_source_hash_is_rejected_before_output(self):
        with self.assertRaisesRegex(ValueError, "size/checksum"):
            self.prepare(lambda url: self.raw + b" ")
        self.assertFalse((self.output / "manifest.json").exists())

    def test_changed_selected_line_cannot_be_accepted_by_repinning_archive_only(self):
        changed = self.raw.replace(b"alpha beta", b"ALPHA BETA")
        self.source["source"].update(sha256=digest(changed), bytes=len(changed)); self.save_source()
        with self.assertRaisesRegex(ValueError, "Selected passage IDs or checksums"):
            self.prepare(lambda url: changed)

    def test_license_card_and_attribution_are_verified(self):
        for filename, message in [("LICENSE", "license checksum"), ("DATASET_CARD.md", "card checksum/license"), ("SOURCE.md", "attribution checksum")]:
            path = self.bundled / filename
            original = path.read_bytes(); path.write_bytes(original + b"changed")
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, message):
                self.prepare()
            path.write_bytes(original)

    def test_modified_document_is_rejected_when_loading(self):
        self.prepare()
        p = self.output / "documents.jsonl"; original = p.read_bytes(); p.write_bytes(original.replace(b"alpha", b"ALPHA"))
        with self.assertRaisesRegex(ValueError, "document checksum"):
            load_documents(self.output)

    def test_not_enough_distinct_contexts_never_pads_the_corpus(self):
        self.source["selection"]["count"] = 4
        with self.assertRaisesRegex(ValueError, "fewer than 4"):
            _select(self.raw, self.source)

    def test_existing_user_files_are_preserved(self):
        self.output.mkdir(); own = self.output / "my-notes.txt"; own.write_text("keep me")
        with self.assertRaisesRegex(ValueError, "unrelated files"):
            self.prepare()
        self.assertEqual(own.read_text(), "keep me")

    def test_chunk_count_matches_paragraph_aware_160_word_packing(self):
        self.assertEqual(_chunk_count(" ".join(["word"] * 320)), 2)
        # Two 100-word paragraphs remain separate, rather than inventing a
        # 160-word chunk crossing this paragraph boundary.
        self.assertEqual(_chunk_count(" ".join(["word"] * 100) + "\n\n" + " ".join(["word"] * 100)), 2)
        self.assertEqual(_chunk_count(" ".join(["word"] * 160)), 1)


if __name__ == "__main__":
    unittest.main()
