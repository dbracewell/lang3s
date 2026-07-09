import enum
from pathlib import Path
from typing import Any, Generator, Optional

from lang3s.core.io.formats.core import BaseSchema, FileFormat, StructuredSchema
from lang3s.core.io.formats.dsv_format import DSVFormat
from lang3s.core.io.formats.json_format import JsonFormat
from lang3s.core.io.formats.text_format import PlainTextFileFormat
from lang3s.core.schemas import File


class InputFileType(enum.StrEnum):
    TEXT = enum.auto()
    MARKDOWN = enum.auto()
    HTML = enum.auto()
    CSV = enum.auto()
    TSV = enum.auto()
    JSON = enum.auto()
    FILE = enum.auto()
    JSON_LINES = enum.auto()
    FILE_LINES = enum.auto()

    @property
    def format(self) -> FileFormat:
        if self == InputFileType.CSV:
            return DSVFormat(delimiter=",")
        elif self == InputFileType.TSV:
            return DSVFormat(delimiter="\t")
        elif self == InputFileType.JSON:
            return JsonFormat(json_lines=False)
        elif self == InputFileType.JSON_LINES:
            return JsonFormat(json_lines=True)
        elif self == InputFileType.TEXT:
            return PlainTextFileFormat(extensions=[".txt"])
        elif self == InputFileType.MARKDOWN:
            return PlainTextFileFormat(
                extensions=[".md"],
                mime_type="text/markdown",
            )
        elif self == InputFileType.HTML:
            return PlainTextFileFormat(
                extensions=[".html"],
                mime_type="text/html",
            )

        raise ValueError(f"{self.value}: Not Implemented")

    def read(
        self,
        file_path: Path | str,
        schema_info: Optional[Path | dict[str, Any]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Generator[File, None, None]:
        total = 0
        for file in self.format.read(Path(file_path), schema_info):
            if offset and total < offset:
                total += 1
                continue
            yield file
            total += 1
            if limit and total >= limit:
                break


__all__ = [
    "InputFileType",
    "FileFormat",
    "BaseSchema",
    "StructuredSchema",
]
