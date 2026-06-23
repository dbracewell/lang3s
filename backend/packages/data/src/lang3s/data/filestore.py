from __future__ import annotations

import enum
import gzip
import json
from pathlib import Path

from lang3s.core import config
from lang3s.data.schemas import Document


class TargetDirectory(str, enum.Enum):
    DOCUMENTS_DIR = "documents"
    ANNOTATIONS_FILE_DIR = "annotations"
    MODELS_DIR = "models"
    AGENT_SESSIONS_DIR = "agent_sessions"


class FileStore:
    def __init__(self):
        self._base = config.FILESTORE_ROOT
        self._base.mkdir(parents=True, exist_ok=True)
        for subdir in TargetDirectory:
            (self._base / subdir).mkdir(parents=True, exist_ok=True)

    def get_directory(self, directory: TargetDirectory) -> Path:
        return self._base / directory

    def write_document(self, doc: Document):
        import msgpack

        document_file_name = (
            self._base / TargetDirectory.DOCUMENTS_DIR.value / f"{doc.id}.msgpack"
        )
        with open(document_file_name, "wb") as fp:
            msgpack.pack(doc.model_dump(), fp)
        return doc.id

    def read_document(self, doc_id: str) -> Document:
        import msgpack

        document_file_name = (
            self._base / TargetDirectory.DOCUMENTS_DIR.value / f"{doc_id}.msgpack"
        )
        with open(document_file_name, "rb") as fp:
            return Document.model_validate(msgpack.unpack(fp))

    def read_annotation_file(self, doc_id: str) -> Document:
        documents_dir = (
            self._base
            / TargetDirectory.ANNOTATIONS_FILE_DIR.value
            / f"{doc_id}.json.gz"
        )
        with gzip.open(documents_dir, "rt", encoding="utf-8") as gzip_fp:
            return json.load(gzip_fp)

    def get_analytics_db_path(self):
        return self._base / "analytics.duckdb"

    def get_file_path(
        self, file_name: str, directory: TargetDirectory | None = None
    ) -> Path:
        if directory is None:
            return self._base / file_name
        else:
            return self._base / directory.value / file_name


filestore = FileStore()
