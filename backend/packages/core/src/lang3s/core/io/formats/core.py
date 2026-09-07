from __future__ import annotations

import abc
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast, override

from pydantic import BaseModel, Field

from lang3s.core.normalizers import normalize_url
from lang3s.core.schemas import File


class BaseSchema(BaseModel):
    mime_type: str = Field(default="text/plain")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_file(
        self,
        index: int,
        row: dict[str, Any],
        path: Path | str | None = None,
    ) -> File | None:
        if "content" not in row:
            return None

        if path is None:
            path = "Generated File"
        else:
            path = str(path)
        row["path"] = path
        new_metadata = self.metadata.copy()
        row_metadata = cast(dict[str, Any], row.get("metadata", {}))
        new_metadata.update(row_metadata)
        row["metadata"] = new_metadata
        row["mime_type"] = self.mime_type
        return File.model_validate(row)


class StructuredSchema(BaseSchema):
    text_column: str
    title_column: str | None = Field(default=None)
    id_column: str | None = Field(default=None)
    id_column_is_url: bool = Field(default=False)
    metadata: dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def from_file(file: str | Path) -> StructuredSchema:
        with open(file) as fp:
            return StructuredSchema.model_validate_json(fp.read())

    @staticmethod
    def from_dict(file: dict[Any, Any]) -> StructuredSchema:
        return StructuredSchema.model_validate(file)

    @override
    def to_file(
        self,
        index: int,
        row: dict[str, Any],
        path: Path | str | None = None,
    ) -> File | None:
        path = Path(path) if path else None

        if path is None:
            path = Path(f"row-{index}")
        else:
            path = Path(f"{path.name}-row-{index}")
        content = cast(str, row[self.text_column])
        if content.strip() == "":
            return None
        metadata = self.metadata.copy()
        metadata["title"] = row[self.title_column] if self.title_column else str(path)
        docId: str | None = row[self.id_column] if self.id_column else None
        if docId and self.id_column_is_url:
            docId = normalize_url(docId)

        return File(
            path=str(path),
            docId=docId,
            content=content,
            mime_type=self.mime_type,
            metadata=metadata,
        )


class FileFormat[T: BaseSchema](abc.ABC):
    def __init__(
        self,
        extensions: list[str],
        schema: type[T],
    ) -> None:
        self.extensions: list[str] = extensions
        self.schema: type[T] = schema

    def _iter_files(self, file_path: Path) -> Generator[Path, None, None]:
        if file_path.is_dir():
            for file in file_path.rglob("**/*"):
                if file.suffix in self.extensions:
                    yield file
        elif file_path.suffix in self.extensions:
            yield file_path

    def read(
        self,
        file_path: Path,
        schema_info: Path | dict[str, Any] | None = None,
    ) -> Generator[File, None, None]:
        active_schema: T
        if schema_info is None:
            active_schema = self.schema()
        elif isinstance(schema_info, dict):
            active_schema = self.schema.model_validate(schema_info)
        else:
            active_schema = self.schema.model_validate(schema_info)
        for path in self._iter_files(file_path):
            for file in self._read_file(path, active_schema):
                yield file

    @abc.abstractmethod
    def _read_file(self, file_path: Path, schema: T) -> Generator[File, None, None]: ...


class StructuredFileFormat[T: StructuredSchema](FileFormat[T], abc.ABC):
    def __init__(
        self,
        extensions: list[str],
        schema: type[T],
    ) -> None:
        super().__init__(extensions, schema)

    @override
    def _read_file(self, file_path: Path, schema: T) -> Generator[File, None, None]:
        index = 0
        for doc in self._read_file_impl(file_path, schema):
            new_file = schema.to_file(index, doc, file_path)
            index += 1
            if new_file:
                yield new_file

    @abc.abstractmethod
    def _read_file_impl(
        self,
        file_path: Path,
        schema: T,
    ) -> Generator[dict[str, Any], None, None]: ...
