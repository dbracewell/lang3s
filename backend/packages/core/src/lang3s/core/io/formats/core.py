from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Generator, Optional, Type, cast

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
        new_metadata.update(row.get("metadata", {}))
        row["metadata"] = new_metadata
        row["mime_type"] = self.mime_type
        return File.model_validate(row)


class StructuredSchema(BaseSchema):
    text_column: str
    title_column: Optional[str] = Field(default=None)
    id_column: Optional[str] = Field(default=None)
    id_column_is_url: bool = Field(default=False)
    metadata: dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def from_file(file: str | Path) -> StructuredSchema:
        with open(file) as fp:
            return StructuredSchema.model_validate_json(fp.read())

    @staticmethod
    def from_dict(file: dict[Any, Any]) -> StructuredSchema:
        return StructuredSchema.model_validate(file)

    def to_file(
        self,
        index: int,
        row: dict[str, Any],
        path: Path | None = None,
    ) -> File | None:
        if path is None:
            path = f"row-{index}"
        else:
            path = f"{path.name}-row-{index}"
        content = cast(str, row[self.text_column])
        if content.strip() == "":
            return None
        metadata = self.metadata.copy()
        metadata["title"] = row[self.title_column] if self.title_column else str(path)
        docId = row[self.id_column] if self.id_column else None
        if docId and self.id_column_is_url:
            docId = normalize_url(docId)
        return File(
            path=path,
            docId=docId,
            content=content,
            mime_type=self.mime_type,
            metadata=metadata,
        )


class FileFormat[T: BaseSchema](abc.ABC):
    def __init__(
        self,
        extensions: list[str],
        schema: Type[T],
    ) -> None:
        self.extensions = extensions
        self.schema = schema

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
        schema_info: Optional[Path | dict[str, Any]] = None,
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


class StructuredFileFormat[T: StructuredSchema](FileFormat):
    def __init__(
        self,
        extensions: list[str],
        schema: Type[T],
    ) -> None:
        super().__init__(extensions, schema)

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
