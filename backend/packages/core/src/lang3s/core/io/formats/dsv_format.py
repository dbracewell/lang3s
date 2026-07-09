from __future__ import annotations

import csv
import traceback
from pathlib import Path
from typing import Any, Generator

from pydantic import Field

from lang3s.core.io.formats.core import (
    StructuredFileFormat,
    StructuredSchema,
)


class CSVSchema(StructuredSchema):
    header: bool = Field(default=True)

    @staticmethod
    def from_file(file: str | Path) -> CSVSchema:
        with open(file) as fp:
            return CSVSchema.model_validate_json(fp.read())

    @staticmethod
    def from_dict(file: dict[Any, Any]) -> CSVSchema:
        return CSVSchema.model_validate(file)


class DSVFormat[T: CSVSchema](StructuredFileFormat):
    def __init__(self, delimiter: str = ",") -> None:
        super().__init__(
            [".csv"] if delimiter == "," else [".tsv"],
            CSVSchema,
        )
        self.delimiter = delimiter

    def _read_file_impl(
        self,
        file_path: Path,
        schema: T,
    ) -> Generator[dict[str, Any], None, None]:
        rows_read = 0
        with open(file_path) as fp:
            reader = (
                csv.DictReader(fp, dialect="excel", delimiter=self.delimiter)
                if schema.header
                else csv.reader(fp, dialect="excel", delimiter=self.delimiter)
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
                )
                traceback.print_exc()
            finally:
                rows_read += 1
