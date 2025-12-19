import argparse
import csv
import enum
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, cast

import jsonlines
from pydantic import BaseModel, Field

from lang3s_job_service import File, JobService


class InputType(str, enum.Enum):
    csv = "csv"
    jsonl = "jsonl"
    json = "json"
    file = "file"
    filejsonl = "filejsonl"


class BaseSchema(BaseModel):

    def to_file(self, index: int, row: Dict[str, Any]):
        return File.model_validate(row)


class StructuredSchema(BaseSchema):
    text_column: str
    title_column: Optional[str]
    metadata: Dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def from_file(file: str | Path) -> "StructuredSchema":
        with open(file) as fp:
            return StructuredSchema.model_validate_json(fp.read())

    @staticmethod
    def from_dict(file: Dict[Any, Any]) -> "StructuredSchema":
        return StructuredSchema.model_validate(file)

    def to_file(self, index: int, row: Dict[str, Any]):
        path = f"file-{index}"
        content = cast(str, row[self.text_column])
        if content.strip() == "":
            return
        metadata = {
            "title": row[self.title_column] if self.title_column else path,
        }
        metadata.update({k: row[cast(str, v)] for k, v in self.metadata.items()})
        return File(
            path=path,
            content=content,
            mime_type="text/plain",
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


# def to_file(
#     index: int,
#     row: Dict[str, Any],
#     schema: BaseSchema,
# ) -> Optional[File]:
#     path = f"file-{index}"
#     content = cast(str, row[schema.text_column])
#     if content.strip() == "":
#         return
#     metadata = {
#         "title": row[schema.title_column] if schema.title_column else path,
#     }
#     metadata.update({k: row[cast(str, v)] for k, v in schema.metadata.items()})
#     return File(
#         path=path,
#         content=content,
#         mime_type="text/plain",
#         metadata=metadata,
#     )


def read_structured_files(
    file: str, schema_file: str | Path, input_type: InputType
) -> List[File]:
    generator = None
    schema = None

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
        new_file = schema.to_file(len(files), doc)  # to_file(len(files), doc, schema)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", help="The source of your documents", required=True
    )
    parser.add_argument(
        "--ext", help="The file extension to limit sources to", required=False
    )
    parser.add_argument(
        "--schema", help="The schema to read in json or csv", required=False
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
    args = parser.parse_args()

    job_service = JobService(
        api_key="lang3skUMvPskpvXQvKVIbsbrQEJFTGvNLjkjGpfIOZmpsMeKVfjWUobFwwmCCUcFeOzxX",
        api_host="http://localhost:3000",
    )

    files: List[File] = []

    if args.type in [InputType.csv, InputType.json, InputType.jsonl, InputType.filejsonl]:
        files = read_structured_files(args.source, args.schema, args.type)
        print(f"Generated {len(files)} and read in {rows_read} rows")

    if args.type == InputType.file:
        files = read_directory(args.source, args.ext)

    if len(files) > 0:
        if args.limit is not None:
            files = files[: args.limit]
        job_service.annotate_documents(files, wait_for_completion=True)

    print(f"Processing {len(files)} files")
