# cython: language_level=3, boundscheck=False, wraparound=False
# src/lang3s/shared_types/metadata_registry.pyx

from threading import RLock

cdef class MetadataRegistry:
    """
    Thread-safe global registry mapping metadata string keys
    to stable integer slot indexes.
    """

    def __cinit__(self):
        self._key_to_index = {}
        self._index_to_key = []
        self._lock = RLock()

    cpdef int ensure_index(self, str key):
        cdef int idx
        with self._lock:
            idx = self._key_to_index.get(key, -1)
            if idx == -1:
                idx = len(self._index_to_key)
                self._index_to_key.append(key)
                self._key_to_index[key] = idx
            return idx

    cpdef int find_index(self, str key):
        return self._key_to_index.get(key, -1)

    cpdef str key_for_index(self, int idx):
        return <str> self._index_to_key[idx]

cdef MetadataRegistry GLOBAL_METADATA_REGISTRY = MetadataRegistry()
