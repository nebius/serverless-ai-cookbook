"""No live calls: recipe URLs must not promise unsupported console parameters."""
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class RecipeLinks(unittest.TestCase):
    def test_two_recipes_and_supported_launch_parameters(self):
        for path, kind in (("training/nemotron-clinical-asr/README.md", "job"),
                           ("templates/endpoint-nemotron-speech/README.md", "endpoint")):
            text = (ROOT / path).read_text()
            links = re.findall(r"https://console\.nebius\.com/serverless/[^)\s]+", text)
            self.assertEqual(len(links), 1)
            url = urlsplit(links[0])
            self.assertEqual(url.path, f"/serverless/{kind}/create")
            query = parse_qs(url.query)
            self.assertLessEqual(set(query), {"image", "platform", "preset", "preemptible", "command", "volumeMountPath", "volumeSize"})
            self.assertEqual(query["volumeMountPath"], ["/data"])
            self.assertNotIn("YOUR_", url.query)

    def test_source_pin_and_no_private_checkpoint(self):
        for path in ("training/nemotron-clinical-asr/Dockerfile", "templates/endpoint-nemotron-speech/Dockerfile"):
            text = (ROOT / path).read_text()
            self.assertIn("db9e31e3ce4f760804b448a846101797111594fa", text)
            self.assertIn("709f6f96c9813fec542a023036d9b06ab8f0f4ec817640d2e06962a5ce920c2e", text)
            self.assertNotIn("2a2b1cae", text)
            self.assertNotIn("e00akg", text)


if __name__ == "__main__":
    unittest.main()
