import sys


def main():
    command = sys.argv.pop(1) if len(sys.argv) > 1 else "serve"
    if command == "cloud-run":
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
    elif command == "serve":
        import uvicorn
        uvicorn.run("clinical_asr.server:app", host="0.0.0.0", port=8000, workers=1, access_log=False)
    else:
        raise SystemExit("Commands: cloud-run, cloud-train, cloud-evaluate, align, segment, train, evaluate, serve")


if __name__ == "__main__":
    main()
