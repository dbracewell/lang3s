from __future__ import annotations

import csv
import traceback
from collections.abc import Generator
from pathlib import Path
from typing import Any, override

from pydantic import Field

from lang3s.core.io.formats.core import (
    StructuredFileFormat,
    StructuredSchema,
)


class CSVSchema(StructuredSchema):
    header: bool = Field(default=True)

    @staticmethod
    @override
    def from_file(file: str | Path) -> CSVSchema:
        with open(file) as fp:
            return CSVSchema.model_validate_json(fp.read())

    @staticmethod
    @override
    def from_dict(file: dict[Any, Any]) -> CSVSchema:  # pyright: ignore[reportExplicitAny]
        return CSVSchema.model_validate(file)


class DSVFormat(StructuredFileFormat[CSVSchema]):
    def __init__(self, delimiter: str = ",") -> None:
        super().__init__(
            [".csv"] if delimiter == "," else [".tsv"],
            CSVSchema,
        )
        self.delimiter: str = delimiter

    @override
    def _read_file_impl(
        self,
        file_path: Path,
        schema: CSVSchema,
    ) -> Generator[dict[str, Any], None, None]:  # pyright: ignore[reportExplicitAny]
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
