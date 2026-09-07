import argparse
import json
import os
from typing import Any

from lang3s.client.job_service import JobService
from lang3s.core.io.formats import InputFileType


def main(
    input_path: str,
    file_type: InputFileType,
    schema_info: str,
):
    print(input_path, file_type, schema_info)
    api_host = os.getenv("LANG3S_API_HOST")
    api_key = os.getenv("LANG3S_API_KEY")

    if not api_host:
        raise RuntimeError("Set LANG3S_API_HOST before running this script.")

    if not api_key:
        raise RuntimeError("Set LANG3S_API_KEY before running this script.")

    jobs = JobService(api_host=api_host, api_key=api_key)
    schema: dict[str, Any] | None = None
    if schema_info:
        with open(schema_info) as fp:
            schema = json.load(fp)

    jobs.annotate(file_type.read(input_path, schema_info=schema))


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Annotate a file using the Lang3s API."
    )
    argument_parser.add_argument(
        "input_path",
        type=str,
        help="Path to the input file to be annotated.",
    )
    argument_parser.add_argument(
        "--file-type",
        type=InputFileType,
        choices=list(InputFileType),
        help="Input file type",
        required=True,
    )
    argument_parser.add_argument(
        "--schema-info",
        type=str,
        help="Path to a JSON file containing schema information for the input file.",
    )
    args = argument_parser.parse_args()
    main(
        input_path=args.input_path,
        file_type=args.file_type,
        schema_info=args.schema_info,
    )
