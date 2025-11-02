import csv
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from pydantic import BaseModel, Field

from lang3s_job_service import File, JobService


class StructuredSchema(BaseModel):
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


def to_file(
    index: int,
    row: Dict[str, str],
    schema: StructuredSchema,
) -> Optional[File]:
    path = f"file-{index}"
    content = cast(str, row[schema.text_column])

    if content.strip() == "":
        return

    metadata = {
        "title": row[schema.title_column] if schema.title_column else path,
    }
    metadata.update({k: row[cast(str, v)] for k, v in schema.metadata.items()})

    return File(
        path=path,
        content=content,
        mime_type="text/plain",
        metadata=metadata,
    )


def read_csv(file: str, schema: StructuredSchema) -> List[File]:
    files = []

    with open(file) as fp:
        reader = csv.DictReader(fp, dialect="excel")
        row_counter = 1
        file_counter = 1
        try:
            for row in reader:
                file = to_file(file_counter, row, schema)
                if file:
                    file_counter += 1
                    files.append(file)
                row_counter += 1
        except Exception:
            print(
                f"Error occurred at row {row_counter}: ",
                end=" ",
                file=sys.stderr,
            )
            traceback.print_exc(0, file=sys.stderr)
            pass

    print(
        f"Created {len(files)} Files, Skipped {row_counter - file_counter} Empty rows"
    )
    return files


if __name__ == "__main__":
    job_service = JobService(
        api_key="lang3skUMvPskpvXQvKVIbsbrQEJFTGvNLjkjGpfIOZmpsMeKVfjWUobFwwmCCUcFeOzxX",
        api_host="http://localhost:3001",
    )

    schema = StructuredSchema.from_file(
        "/Users/ik/prj/Lang3s/backend/jobs_service/data_schema.json"
    )
    files: List[File] = read_csv("/Users/ik/Downloads/archive/data.csv", schema)
