import json
import traceback
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast, override

from lang3s.core.io import jsonlines_reader
from lang3s.core.io.formats.core import (
    StructuredFileFormat,
    StructuredSchema,
)


class JsonFormat(StructuredFileFormat[StructuredSchema]):
    def __init__(self, json_lines: bool = False) -> None:
        super().__init__(
            [".jsonl"] if json_lines else [".json"],
            StructuredSchema,
        )
        self.json_lines: bool = json_lines

    def _json_reader(
        self,
        file_path: Path,
    ) -> Generator[dict[str, Any], None, None]:
        rows_read = 0
        with open(file_path) as fp:
            doc = json.load(fp)
            try:
                for row in doc:
                    doc = cast(dict[str, Any], row)
                    yield doc
            except Exception:
                print(
                    f"Error occurred at row {rows_read}: ",
                    end=" ",
                )
                traceback.print_exc()
            finally:
                rows_read += 1

    def _json_lines_reader(
        self,
        file_path: Path,
    ) -> Generator[dict[str, Any], None, None]:
        for doc in jsonlines_reader(file_path):
            yield doc

    @override
    def _read_file_impl(
        self,
        file_path: Path,
        schema: StructuredSchema,
    ) -> Generator[dict[str, Any], None, None]:
        generator = self._json_reader
        if self.json_lines:
            generator = self._json_lines_reader
        for doc in generator(file_path):
            yield doc
