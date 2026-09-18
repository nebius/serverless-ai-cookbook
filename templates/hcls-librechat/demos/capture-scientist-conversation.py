"""Save actual browser-created conversations and tool traces without credentials."""
import argparse
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
        for name, path in {
            "messages": "/api/messages/" + args.conversation,
            "tool-calls": "/api/agents/tools/calls?conversationId=" + args.conversation,
            "chat-status": "/api/agents/chat/status/" + args.conversation,
        }.items():
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
        (args.output / "receipt.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
