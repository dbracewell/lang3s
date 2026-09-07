import enum
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

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
    def file_format(self) -> FileFormat[BaseSchema]:
        if self == InputFileType.CSV:
            return cast(FileFormat[BaseSchema], DSVFormat(delimiter=","))
        elif self == InputFileType.TSV:
            return cast(FileFormat[BaseSchema], DSVFormat(delimiter="\t"))
        elif self == InputFileType.JSON:
            return cast(FileFormat[BaseSchema], JsonFormat(json_lines=False))
        elif self == InputFileType.JSON_LINES:
            return cast(FileFormat[BaseSchema], JsonFormat(json_lines=True))
        elif self == InputFileType.TEXT:
            return cast(
                FileFormat[BaseSchema], PlainTextFileFormat(extensions=[".txt"])
            )
        elif self == InputFileType.MARKDOWN:
            return cast(
                FileFormat[BaseSchema],
                PlainTextFileFormat(
                    extensions=[".md"],
                    mime_type="text/markdown",
                ),
            )
        elif self == InputFileType.HTML:
            return cast(
                FileFormat[BaseSchema],
                PlainTextFileFormat(
                    extensions=[".html"],
                    mime_type="text/html",
                ),
            )

        raise ValueError(f"{self.value}: Not Implemented")

    def read(
        self,
        file_path: Path | str,
        schema_info: Path | dict[str, Any] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Generator[File, None, None]:
        total = 0
        for file in self.file_format.read(Path(file_path), schema_info):
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
