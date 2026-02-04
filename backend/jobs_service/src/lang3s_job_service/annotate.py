from __future__ import annotations

import argparse
import csv
import enum
import json
import math
import os
import sys
import traceback
from pathlib import Path
from time import strftime
from typing import Any, Dict, Generator, List, Optional, cast

import jsonlines
import shortuuid
from pydantic import BaseModel, Field
from url_normalize import url_normalize

from lang3s_job_service import File, JobService


def normalize_url(url_string):
    """
    Normalizes a given URL string using the url-normalize library.

    Args:
        url_string: The URL string to normalize.

    Returns:
        The normalized URL string, or None if the input is not a valid URL.
    """
    try:
        normalized = url_normalize(url_string)
        return normalized
    except Exception as e:
        print(f"Error normalizing URL: {e}")
        return url_string


class InputType(str, enum.Enum):
    csv = "csv"
    jsonl = "jsonl"
    json = "json"
    file = "file"
    filejsonl = "filejsonl"


class BaseSchema(BaseModel):
    def to_file(self, index: int, row: Dict[str, Any], mime_type: str) -> File | None:
        if "metadata" not in row:
            row["metadata"] = dict()
        row["mime_type"] = mime_type
        return File.model_validate(row)


class StructuredSchema(BaseSchema):
    text_column: str
    id_column: Optional[str] = Field(default=None)
    id_column_is_url: bool = Field(default=False)
    title_column: Optional[str] = Field(default=None)
    metadata: Dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def from_file(file: str | Path) -> StructuredSchema:
        try:
            with open(file) as fp:
                return StructuredSchema.model_validate_json(fp.read())
        except Exception as e:
            traceback.print_exc(0, file=sys.stderr)
            raise e

    @staticmethod
    def from_dict(file: Dict[Any, Any]) -> StructuredSchema:
        return StructuredSchema.model_validate(file)

    def to_file(self, index: int, row: Dict[str, Any], mime_type: str) -> File | None:
        path = f"file-{index}"
        content = cast(str, row[self.text_column])
        if content.strip() == "":
            return None
        metadata = {
            "title": row[self.title_column] if self.title_column else path,
        }
        metadata.update({k: row[v] for k, v in self.metadata.items()})
        docId = row[self.id_column] if self.id_column else None
        if docId and self.id_column_is_url:
            docId = normalize_url(docId)
        return File(
            path=path,
            docId=docId,
            content=content,
            mime_type=mime_type,
            metadata=metadata,
        )


class CSVSchema(StructuredSchema):
    header: bool = Field(default=True)

    @staticmethod
    def from_file(file: str | Path) -> "CSVSchema":
        with open(file) as fp:
            return CSVSchema.model_validate_json(fp.read())

    @staticmethod
    def from_dict(file: Dict[Any, Any]) -> "CSVSchema":
        return CSVSchema.model_validate(file)


rows_read = 0


def read_structured_files(
    file: str,
    schema_file: str | Path,
    input_type: InputType,
    mime_type: str,
) -> List[File]:
    if input_type == InputType.csv:
        schema = CSVSchema.from_file(schema_file)
        generator = csv_row_generator(file, schema)
    elif input_type == InputType.json:
        schema = StructuredSchema.from_file(args.schema)
        generator = json_row_generator(file)
    elif input_type == InputType.jsonl:
        schema = StructuredSchema.from_file(args.schema)
        generator = jsonl_row_generator(file)
    elif input_type == InputType.filejsonl:
        schema = BaseSchema()
        generator = jsonl_row_generator(file)
    else:
        raise Exception(f"{input_type} is not supported")

    files = []
    for doc in generator:
        new_file = schema.to_file(len(files), doc, mime_type)
        if new_file:
            files.append(new_file)
    return files


def csv_row_generator(
    csv_file: str, schema: CSVSchema
) -> Generator[Dict[str, Any], None, None]:
    global rows_read
    with open(csv_file) as fp:
        reader = (
            csv.DictReader(fp, dialect="excel")
            if schema.header
            else csv.reader(fp, dialect="excel")
        )
        try:
            for row in reader:
                if isinstance(row, list):
                    row = {f"{i}": v for i, v in enumerate(row)}
                yield row
        except Exception:
            print(
                f"Error occurred at row {rows_read}: ",
                end=" ",
                file=sys.stderr,
            )
            traceback.print_exc(0, file=sys.stderr)
        finally:
            rows_read += 1


def jsonl_row_generator(
    json_file: str,
) -> Generator[Dict[str, Any], None, None]:
    global rows_read
    with jsonlines.open(json_file) as reader:
        try:
            for row in reader:
                doc = cast(Dict[str, Any], row)
                yield doc
        except Exception:
            print(
                f"Error occurred at row {rows_read}: ",
                end=" ",
                file=sys.stderr,
            )
            traceback.print_exc(0, file=sys.stderr)
        finally:
            rows_read += 1


def json_row_generator(json_file: str) -> Generator[Dict[str, Any], None, None]:
    global rows_read
    with open(json_file) as fp:
        doc = json.load(fp)
        try:
            for row in doc:
                doc = cast(Dict[str, Any], row)
                yield doc
        except Exception:
            print(
                f"Error occurred at row {rows_read}: ",
                end=" ",
                file=sys.stderr,
            )
            traceback.print_exc(0, file=sys.stderr)
        finally:
            rows_read += 1


def read_directory(file: str, ext: str | None) -> List[File]:
    files: List[File] = []
    if ext is None:
        ext = ""
    ext = ext.lower()
    if os.path.isdir(file):
        for child in os.listdir(file):
            full_path = os.path.join(file, child)
            if os.path.isfile(full_path) and os.path.basename(
                full_path
            ).lower().endswith(ext):
                files.append(File(path=full_path, content=""))
    return files


import random
from datetime import datetime, timedelta


def random_datetime_between(start_date, end_date):
    """
    Generate a random datetime between two datetime objects.
    """
    delta = end_date - start_date
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start_date + timedelta(seconds=random_second)


# Example Usage
d1 = datetime.strptime("1/1/2000 1:30 AM", "%m/%d/%Y %I:%M %p")
d2 = datetime.strptime("1/1/2025 4:50 AM", "%m/%d/%Y %I:%M %p")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="The source of your documents", required=True)
    parser.add_argument(
        "--ext", help="The file extension to limit sources to", required=False
    )
    parser.add_argument(
        "--schema", help="The schema to read in json or csv", required=False
    )
    parser.add_argument(
        "--mime-type",
        help="The MIME type to use for files",
        default="text/plain",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limits the number of documents annotated",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--type",
        type=InputType,
        help="The input type",
        choices=list(InputType),
        required=True,
    )
    parser.add_argument(
        "--wait",
        help="Wait for the job to complete",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    job_service = JobService(
        api_key="lang3sIDDtzpFlQvyWqeFxXSvcBJkEoLQvjhAuyiNrnUDhrGxjFEpqkrHZhwToGtpvqkPT",
        api_host="http://localhost:3000",
    )

    files: List[File] = []

    if args.type in [
        InputType.csv,
        InputType.json,
        InputType.jsonl,
        InputType.filejsonl,
    ]:
        files = read_structured_files(
            args.source, args.schema, args.type, args.mime_type
        )
        print(f"Generated {len(files)} and read in {rows_read} rows")

    if args.type == InputType.file:
        files = read_directory(args.source, args.ext)

    if len(files) > 0:
        if args.limit is not None:
            files = files[: args.limit]
        for file in files:
            file.metadata["published_data"] = random_datetime_between(d1, d2).strftime(
                "%Y-%m-%d %H:%M:%S",
            )
            file.metadata["int_data"] = random.randint(0, 100)
            file.metadata["float_data"] = random.random()
            file.metadata["string_array_data"] = [
                shortuuid.uuid() for _ in range(random.randint(1, 10))
            ]
        job_service.annotate_documents(files, wait_for_completion=args.wait)

    print(f"Processing {len(files)} files")
