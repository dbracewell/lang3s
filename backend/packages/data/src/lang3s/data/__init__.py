from __future__ import annotations

from typing import Any

__all__ = ["filestore"]


class _LazyFileStore:
    """Proxy that defers FileStore initialization until first attribute access."""

    def __getattr__(self, item: str) -> Any:
        from .filestore import filestore as _filestore

        return getattr(_filestore, item)


filestore = _LazyFileStore()
