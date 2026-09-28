import importlib.util
import json
import tempfile
import unittest
import wave
from pathlib import Path

spec = importlib.util.spec_from_file_location("recipe_train", Path(__file__).with_name("train.py"))
train = importlib.util.module_from_spec(spec)
spec.loader.exec_module(train)


class Inputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "audio").mkdir()
        for name in ("a", "b"):
            with wave.open(str(self.root / "audio" / (name + ".wav")), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes((b"\1\0" if name == "a" else b"\2\0") * 16000)
        self.a = {"audio_filepath": "audio/a.wav", "text": "Human transcript.", "conversation_id": "a"}
        self.b = {**self.a, "audio_filepath": "audio/b.wav", "conversation_id": "b"}
        self.write(self.a, self.b)

    def write(self, a, b):
        for name, row in (("train", a), ("validation", b)):
            (self.root / (name + ".jsonl")).write_text(json.dumps(row) + "\n")

    def test_valid(self):
        a, b = train.inputs(self.root)
        self.assertEqual(a[0]["duration"], 1)
        self.assertEqual(b[0]["text"], "Human transcript.")

    def test_wrong_fields_and_empty_text(self):
        for row in ({**self.a, "text": " "}, {**self.a, "unreviewed": 1}):
            self.write(row, self.b)
            with self.assertRaises(ValueError):
                train.inputs(self.root)

    def test_split_conversation_and_audio(self):
        for row in ({**self.b, "conversation_id": "a"}, {**self.b, "audio_filepath": "audio/a.wav"}):
            self.write(self.a, row)
            with self.assertRaises(ValueError):
                train.inputs(self.root)

    def test_paths(self):
        for value in ("../audio/a.wav", "/tmp/a.wav", "audio/../a.wav"):
            self.write({**self.a, "audio_filepath": value}, self.b)
            with self.assertRaises(ValueError):
                train.inputs(self.root)

    def test_empty_and_wrong_wav(self):
        (self.root / "train.jsonl").write_text("")
        with self.assertRaises(ValueError):
            train.inputs(self.root)
        self.write(self.a, self.b)
        with wave.open(str(self.root / "audio/a.wav"), "wb") as wav:
            wav.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0" * 32000)
        with self.assertRaises(ValueError):
            train.inputs(self.root)

    def test_existing_output_and_invalid_budget_before_gpu(self):
        for steps, rate in ((0, 1e-4), (10, float("nan"))):
            with self.assertRaises(ValueError):
                train.run(self.root, self.root / "out", steps, rate)
        with self.assertRaises(FileExistsError):
            train.run(self.root, self.root, 10, 1e-4)

    def test_truncated_and_same_content_audio(self):
        a, b = self.root / "audio/a.wav", self.root / "audio/b.wav"
        b.write_bytes(a.read_bytes() + b"different metadata; identical PCM")
        with self.assertRaises(ValueError):
            train.inputs(self.root)
        a.write_bytes(a.read_bytes()[:44])
        with self.assertRaises(ValueError):
            train.inputs(self.root)

    def test_real_nemo_template(self):
        from omegaconf import OmegaConf
        import os
        root = Path(os.environ.get("NEMO_SOURCE", "/opt/nemo"))
        template = OmegaConf.load(root / "examples/asr/conf/fastconformer/cache_aware_streaming/fastconformer_transducer_bpe_streaming.yaml")
        for training in (True, False):
            cfg = train.dataset_config(template, training)
            self.assertEqual(cfg.sample_rate, 16000)
            self.assertFalse(cfg.fault_tolerant_audio_loading)


if __name__ == "__main__":
    unittest.main()
