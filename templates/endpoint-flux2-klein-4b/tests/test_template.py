"""Check deployment links and execute the README curl examples against a stub API."""
import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
IMAGE = "vllm/vllm-omni:v0.24.0@sha256:566d89d7eaba08dd313dab2464e67fe984825d281c77437582e3008a917bbf7c"
SERVE_ARGS = (
    "serve black-forest-labs/FLUX.2-klein-4B --omni --host 0.0.0.0 --port 8000 "
    "--revision e7b7dc27f91deacad38e78976d1f2b499d76a294"
)
EXPECTED_DEPLOY = {
    "image": [IMAGE],
    "command": ["vllm " + SERVE_ARGS],
    "targetPort": ["8000"],
    "platform": ["gpu-l40s-a"],
    "preset": ["1gpu-16vcpu-64gb"],
    "diskSize": ["500GiB"],
    "preemptible": ["false"],
    "auth": ["true"],
}
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aMxkAAAAASUVORK5CYII=')


class TemplateTests(unittest.TestCase):
    def test_deployment_contract(self):
        def links(path):
            raw = re.findall(r'https://console\.nebius\.com/serverless/endpoint/create\?[^"\s)]+', path.read_text())
            return [parse_qs(urlsplit(html.unescape(u)).query) for u in raw if 'FLUX.2-klein-4B' in u]
        self.assertEqual(links(ROOT / 'README.md'), [EXPECTED_DEPLOY])
        self.assertEqual(links(REPO / 'README.md'), [EXPECTED_DEPLOY])
        self.assertEqual(links(REPO / 'templates/README.md'), [EXPECTED_DEPLOY] * 2)

        blocks = re.findall(r'```bash\n(.*?)```', (ROOT / 'README.md').read_text(), re.S)
        command = next(b for b in blocks if 'nebius ai endpoint create' in b)
        args = shlex.split(command.replace('\\\n', ''))
        self.assertEqual(args[:4], ['nebius', 'ai', 'endpoint', 'create'])
        expected_cli = {
            '--name': 'flux2-klein-4b',
            '--image': IMAGE,
            '--platform': EXPECTED_DEPLOY['platform'][0],
            '--preset': EXPECTED_DEPLOY['preset'][0],
            '--container-port': EXPECTED_DEPLOY['targetPort'][0],
            '--disk-size': '500Gi',
            '--shm-size': '16Gi',
            '--auth': 'token',
            '--container-command': 'vllm',
            '--args': SERVE_ARGS,
        }
        for flag, expected in expected_cli.items():
            with self.subTest(cli_flag=flag):
                self.assertEqual(args.count(flag), 1)
                self.assertEqual(args[args.index(flag) + 1], expected)
        self.assertEqual({arg for arg in args if arg.startswith('--')}, set(expected_cli) | {'--public'})
        self.assertIn('--public', args)
        self.assertNotIn('--preemptible', args)

    def test_readme_curl_generation_and_editing(self):
        received = []
        readiness_responses = [200]
        readiness_calls = []

        class API(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                status = readiness_responses.pop(0) if readiness_responses else 500
                readiness_calls.append(status)
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'data': [{'id': 'black-forest-labs/FLUX.2-klein-4B'}]}).encode())

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                received.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), API)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        text = (ROOT / 'README.md').read_text()
        blocks = re.findall(r'```bash\n(.*?)```', text, re.S)
        snippets = [b for b in blocks if 'curl --fail-with-body' in b]
        self.assertEqual(len(snippets), 2)
        setup = f'BASE_URL=http://127.0.0.1:{server.server_port}\nAUTH=(-H "Authorization: Bearer test-token")\n'
        try:
            with tempfile.TemporaryDirectory() as directory:
                readiness = next(b for b in blocks if 'ready=false' in b)
                subprocess.run(['bash', '-euo', 'pipefail', '-c', setup + readiness],
                               cwd=directory, check=True, capture_output=True)
                for statuses in ([401], [403], [502, 200]):
                    with self.subTest(readiness_statuses=statuses):
                        readiness_responses[:] = statuses
                        readiness_calls.clear()
                        result = subprocess.run(
                            ['bash', '-euo', 'pipefail', '-c', setup + 'sleep() { :; }\n' + readiness],
                            cwd=directory, text=True, capture_output=True, timeout=5)
                        self.assertEqual(readiness_calls, statuses)
                        self.assertEqual(result.returncode, 0 if statuses[-1] == 200 else 1)
                        if statuses[-1] != 200:
                            self.assertIn('Authentication failed', result.stderr)
                            self.assertNotIn('timed out', result.stderr)
                for snippet in snippets:
                    subprocess.run(['bash', '-euo', 'pipefail', '-c', setup + snippet], cwd=directory, check=True)
                self.assertEqual((Path(directory) / 'klein-generated.png').read_bytes(), PNG)
                self.assertEqual((Path(directory) / 'klein-edited.png').read_bytes(), PNG)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual([r[0] for r in received], ['/v1/images/generations', '/v1/images/edits'])
        self.assertTrue(all(r[1] == 'Bearer test-token' for r in received))
        generation = json.loads(received[0][2])
        self.assertEqual((generation['num_inference_steps'], generation['guidance_scale']), (4, 1.0))
        self.assertEqual(generation['model'], 'black-forest-labs/FLUX.2-klein-4B')
        self.assertIn(b'name="image"; filename="klein-generated.png"', received[1][2])
        self.assertIn(PNG, received[1][2])


if __name__ == '__main__':
    unittest.main()
