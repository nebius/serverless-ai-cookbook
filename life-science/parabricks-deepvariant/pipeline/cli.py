import os
import sys
from pathlib import Path

from pipeline import run

REQUIRED_VARS = (
    "S3_BUCKET", "S3_ENDPOINT_URL", "S3_INPUT_PREFIX", "S3_REF_PREFIX",
    "S3_OUTPUT_PREFIX", "SAMPLE_ID",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION",
)


def validate_env() -> None:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}")


def main(scratch: str = "/scratch") -> None:
    validate_env()
    run.run_germline(Path(scratch))


if __name__ == "__main__":
    main()
