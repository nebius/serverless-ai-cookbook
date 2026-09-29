"""No live calls: recipe URLs must not promise unsupported console parameters."""
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TRAIN_README = "training/nemotron-clinical-asr/README.md"
SERVE_README = "templates/endpoint-nemotron-speech/README.md"
REGISTRY = "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/"
TRAIN_IMAGE = REGISTRY + "nemotron-speech-train@sha256:1a5756455cb3f6a763887511df205648cf1c53afbfc694d0ae6c0f605cb85f67"
SERVE_IMAGE = REGISTRY + "nemotron-speech-serve@sha256:62f58367ce6247f4a9e6a2ee255cd607038796d73f5a2583e068f6bdf8498a32"


def buttons(path):
    return re.findall(r"\[!\[([^\]]+)\]\(([^)]+)\)\]\((https://console\.nebius\.com/serverless/[^)\s]+)\)",
                      (ROOT / path).read_text())


class RecipeLinks(unittest.TestCase):
    def test_two_recipes_and_supported_launch_parameters(self):
        for path, kind, image, commands in (
            (TRAIN_README, "job", TRAIN_IMAGE, ["python /opt/recipe/train.py"]),
            (SERVE_README, "endpoint", SERVE_IMAGE,
             ["python /opt/recipe/serve.py", "python /opt/recipe/serve.py --checkpoint /data/runs/YOUR_RUN"]),
        ):
            found = buttons(path)
            self.assertEqual(len(found), len(commands))
            for (_, asset, link), command in zip(found, commands, strict=True):
                self.assertTrue((ROOT / path).parent.joinpath(asset).is_file())
                url = urlsplit(link)
                self.assertEqual((url.scheme, url.netloc, url.path),
                                 ("https", "console.nebius.com", f"/serverless/{kind}/create"))
                self.assertFalse(url.fragment)
                # Exact keys prevent accidental secrets or unsupported console parameters.
                self.assertEqual(parse_qs(url.query, strict_parsing=True, keep_blank_values=True), {
                    "image": [image], "platform": ["gpu-h100-sxm"],
                    "preset": ["1gpu-16vcpu-200gb"], "preemptible": ["false"],
                    "command": [command], "volumeMountPath": ["/data"], "volumeSize": ["100"],
                })

    def test_tuned_choice_is_explicit_and_not_a_stock_fallback(self):
        text = (ROOT / SERVE_README).read_text()
        found = buttons(SERVE_README)
        self.assertEqual([label for label, _, _ in found],
                         ["Create stock Endpoint", "Create fine-tuned Endpoint"])
        self.assertNotIn("YOUR_", found[0][2])
        self.assertNotIn("YOUR_", buttons(TRAIN_README)[0][2])
        self.assertIn("Replace `YOUR_RUN` in the form's command before creating", text)
        self.assertIn("reads and verifies the sibling `model.sha256`", text)
        self.assertIn("does not fall back to stock weights", text)

    def test_validation_scope_remains_explicit(self):
        for path in (TRAIN_README, SERVE_README):
            text = (ROOT / path).read_text()
            self.assertNotIn("Image publication pending", text)
            self.assertIn("CPU tests and imports", text)
            self.assertIn("No new GPU training or endpoint validation", text)
            self.assertNotIn("one-click", text.lower())

    def test_source_pin_and_no_private_checkpoint(self):
        for path in ("training/nemotron-clinical-asr/Dockerfile", "templates/endpoint-nemotron-speech/Dockerfile"):
            text = (ROOT / path).read_text()
            self.assertIn("db9e31e3ce4f760804b448a846101797111594fa", text)
            self.assertIn("709f6f96c9813fec542a023036d9b06ab8f0f4ec817640d2e06962a5ce920c2e", text)
            self.assertNotIn("2a2b1cae", text)
            self.assertNotIn("e00akg", text)


if __name__ == "__main__":
    unittest.main()
