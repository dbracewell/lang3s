from pathlib import Path
from typing import Generator

from lang3s.core.io.formats.core import BaseSchema, FileFormat
from lang3s.core.schemas import File


class PlainTextFileFormat[T: BaseSchema](FileFormat):
    def __init__(
        self,
        extensions: list[str],
        encoding: str = "utf-8",
        mime_type: str = "text/plain",
    ) -> None:
        super().__init__(extensions, BaseSchema)
        self._encoding = encoding
        self._mime_type = mime_type

    def _read_file(self, file_path: Path, schema: T) -> Generator[File, None, None]:
        content = file_path.read_text(encoding=self._encoding)
        effective_metadata = schema.metadata.copy()
        effective_metadata["title"] = file_path.name
        yield File(
            content=content,
            mime_type=self._mime_type,
            path=str(file_path),
            metadata=effective_metadata,
        )
