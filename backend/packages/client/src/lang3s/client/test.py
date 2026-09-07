import os
from pathlib import Path

from lang3s.client.job_service import JobService
from lang3s.core.io.formats import InputFileType


def main():
    api_host = os.getenv("LANG3S_API_HOST", "http://localhost:8003")
    api_key = os.getenv("LANG3S_API_KEY")
    input_path = Path(os.getenv("LANG3S_INPUT_JSONL", "./news.jsonl"))

    if not api_key:
        raise RuntimeError("Set LANG3S_API_KEY before running this script.")

    jobs = JobService(api_host=api_host, api_key=api_key)
    jobs.annotate(
        InputFileType.JSON_LINES.read(
            str(input_path),
            schema_info={"text_column": "content"},
        )
    )


if __name__ == "__main__":
    main()
