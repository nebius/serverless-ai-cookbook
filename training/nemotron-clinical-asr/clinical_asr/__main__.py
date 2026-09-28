import sys

USAGE = """Commands: cloud-run, cloud-train, cloud-evaluate, align, segment, train, evaluate, evaluate-english, serve

For multi-customer serving, use shared-runtime (see SHARED_SERVING.md).
The explicit 'serve' command is a single-active research diagnostic only.
No command starts automatically.
"""


def main():
    command = sys.argv.pop(1) if len(sys.argv) > 1 else "--help"
    if command in {"help", "--help", "-h"}:
        print(USAGE)
    elif command == "cloud-run":
        from .cloud import main
        main()
    elif command == "cloud-train":
        from .cloud_train import main
        main()
    elif command == "cloud-evaluate":
        from .cloud_evaluate import main
        main()
    elif command == "align":
        from .prepare import align_main
        align_main()
    elif command == "segment":
        from .prepare import segment_main
        segment_main()
    elif command == "train":
        from .train import main
        main()
    elif command == "evaluate":
        from .evaluate import main
        main()
    elif command == "evaluate-english":
        from .evaluate_english import main
        main()
    elif command == "serve":
        import uvicorn
        uvicorn.run("clinical_asr.server:app", host="0.0.0.0", port=8000, workers=1, access_log=False)
    else:
        raise SystemExit(USAGE)


if __name__ == "__main__":
    main()
