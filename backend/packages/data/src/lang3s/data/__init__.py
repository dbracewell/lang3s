from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .filestore import FileStore

__all__ = ["filestore"]


def __getattr__(name: str):
    """Lazily import filestore to avoid side effects at package import time."""
    if name == "filestore":
        from .filestore import filestore

        return filestore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
