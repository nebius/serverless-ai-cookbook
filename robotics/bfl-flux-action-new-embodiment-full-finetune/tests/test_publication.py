"""Check artifact publication with tiny files and stubbed GPU dependencies."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class TrainerStub:
    def __init__(self, config):
        self.output_dir = config.output_dir

    def _checkpoint(self):
        pass


# Only external training dependencies are stubbed; filesystem publication is real.
with patch.dict(sys.modules, {
    "torch": SimpleNamespace(cuda=SimpleNamespace(device_count=Mock(return_value=1))),
    "flux_action.training.checkpoint": SimpleNamespace(export_policy=Mock(), latest_checkpoint=Mock()),
    "flux_action.training.distributed": SimpleNamespace(init_distributed=Mock()),
    "flux_action.training.trainer": SimpleNamespace(TrainConfig=Mock(), Trainer=TrainerStub),
    "prepare": SimpleNamespace(prepare=Mock()),
}):
    spec = importlib.util.spec_from_file_location("aloha_train_job", ROOT / "src/train_job.py")
    train_job = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(train_job)


class PublicationTests(unittest.TestCase):
    def test_checkpoint_marker_is_copied_last_and_absent_on_copy_failure(self):
        for truncated in (False, True):
            with self.subTest(truncated=truncated), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                checkpoint = root / "local/step-4"
                checkpoint.mkdir(parents=True)
                (checkpoint / "weights.bin").write_bytes(b"checkpoint weights")
                (checkpoint / "COMPLETE").write_text("4\n")
                (checkpoint.parent / "metrics.jsonl").write_text('{"step": 4}\n')
                destination = root / "bucket"
                marker = destination / "checkpoints/step-4/COMPLETE"
                copyfile = train_job.shutil.copyfile

                def copy(source, target):
                    if Path(source).parent == checkpoint:
                        self.assertFalse(marker.exists())
                        if Path(source).name == "COMPLETE":
                            self.assertEqual((marker.parent / "weights.bin").read_bytes(), b"checkpoint weights")
                    if truncated:
                        Path(target).write_bytes(b"x")
                    else:
                        return copyfile(source, target)

                trainer = train_job.PublishingTrainer(SimpleNamespace(output_dir=checkpoint.parent), destination)
                with patch.object(train_job, "latest_checkpoint", return_value=checkpoint), \
                        patch.object(train_job.shutil, "copyfile", side_effect=copy):
                    if truncated:
                        with self.assertRaisesRegex(IOError, "incomplete copy"):
                            trainer._checkpoint()
                        self.assertFalse(marker.exists())
                    else:
                        trainer._checkpoint()
                        self.assertEqual(marker.read_text(), "4\n")

    def test_export_receipt_requires_successful_copy_and_records_hash(self):
        for truncated in (False, True):
            with self.subTest(truncated=truncated), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                work = root / "work"
                work.mkdir()
                runs = root / "runs"
                result = runs / "test-run"
                result.mkdir(parents=True)
                (result / "PREPARED.json").write_text("{}")
                checkpoint = root / "local/step-4"
                checkpoint.mkdir(parents=True)
                config = SimpleNamespace(output_dir=checkpoint.parent, steps=4)
                weights = b"exported BF16 weights"

                def export(source, output, **kwargs):
                    output.mkdir()
                    (output / "model.safetensors").write_bytes(weights)
                    (output / "config.json").write_text("{}")

                with patch.dict(os.environ, {"RUN_NAME": "test-run"}), \
                        patch.object(train_job, "WORK", work), \
                        patch.object(train_job, "Path", side_effect=lambda value: runs if value == "/workspace/data/runs" else Path(value)), \
                        patch.object(train_job.TrainConfig, "from_file", return_value=config), \
                        patch.object(train_job.PublishingTrainer, "run", create=True), \
                        patch.object(train_job, "latest_checkpoint", return_value=checkpoint), \
                        patch.object(train_job, "export_policy", side_effect=export):
                    if truncated:
                        with patch.object(train_job.shutil, "copyfile",
                                          side_effect=lambda source, target: Path(target).write_bytes(b"x")):
                            with self.assertRaisesRegex(IOError, "incomplete copy"):
                                train_job.worker()
                        self.assertFalse((result / "TRAIN_COMPLETE.json").exists())
                    else:
                        train_job.worker()
                        receipt = json.loads((result / "TRAIN_COMPLETE.json").read_text())
                        self.assertEqual(receipt["export_model_sha256"], hashlib.sha256(weights).hexdigest())
                        self.assertEqual(receipt["optimizer_updates"], 4)
                        self.assertEqual((result / "export/model.safetensors").read_bytes(), weights)


if __name__ == "__main__":
    unittest.main()
