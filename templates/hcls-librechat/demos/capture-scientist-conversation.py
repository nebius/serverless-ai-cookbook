"""Privately preserve browser conversations, tool traces and real deliverables.

Login credentials are never printed or copied, but raw tool traces can contain
short-lived signed artifact URLs. Keep the entire output directory private.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workbenches", required=True, type=Path)
    parser.add_argument("--scientist", required=True)
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workspace-file", action="append", default=[], help="Download an actual study deliverable for independent verification.")
    parser.add_argument("--workspace-list", action="append", default=[], help="Record actual directory entries before checking claimed file names.")
    parser.add_argument('--runs', action='store_true', help='Capture current caller-scoped Runs and workshop statuses read-only.')
    args = parser.parse_args()
    os.umask(0o077)
    person = next(item for item in json.loads(args.manifest.read_text())["scientists"]
                  if item["id"] == args.scientist)
    deployment = json.loads((args.workbenches / args.scientist / "deployment.json").read_text())
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with httpx.Client(base_url=deployment["url"], timeout=120) as client:
        response = client.post("/api/auth/login", json={"email": person["email"], "password": person["password"]})
        response.raise_for_status()
        client.headers["authorization"] = "Bearer " + response.json()["token"]
        summary = {"scientist_id": args.scientist, "conversation_id": args.conversation,
                   "endpoint_id": deployment["endpoint_id"], "image": deployment["image"], "files": {}}
        endpoints = {
            "messages": "/api/messages/" + args.conversation,
            "tool-calls": "/api/agents/tools/calls?conversationId=" + args.conversation,
            "chat-status": "/api/agents/chat/status/" + args.conversation,
        }
        if args.runs:
            endpoints.update({'runs': '/api/scientific-demos/runs',
                              'workshop-runs': '/api/scientific-demos/workshop/runs'})
        for name, path in endpoints.items():
            response = client.get(path)
            response.raise_for_status()
            try:
                value = response.json()
            except ValueError:
                value = {"status": response.status_code, "content_type": response.headers.get("content-type"),
                         "body": response.text}
            target = args.output / (name + ".json")
            with target.open("w") as stream:
                json.dump(value, stream, indent=2)
                stream.write("\n")
            summary["files"][name] = {"bytes": target.stat().st_size}
        for relative in args.workspace_file:
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('Use workspace-relative deliverable paths.')
            response = client.get('/api/scientific-demos/workspace/file', params={'path': relative})
            if response.status_code != 200:
                summary['files'][relative] = {'status': response.status_code, 'missing': True}
                continue
            target = args.output / 'workspace' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            summary['files'][relative] = {'bytes': len(response.content), 'sha256': hashlib.sha256(response.content).hexdigest()}
        for index, relative in enumerate(args.workspace_list):
            response = client.get('/api/scientific-demos/workspace', params={'path': relative})
            response.raise_for_status()
            target = args.output / f'workspace-list-{index}.json'
            target.write_text(json.dumps(response.json(), indent=2) + '\n')
            summary['files'][relative + '/'] = {'listing': target.name}
        (args.output / "receipt.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
