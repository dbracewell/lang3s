# cython: language_level=3, boundscheck=False, wraparound=False
# list_metadata.pyx


# @formatter:off
#type: ignore
from lang3s.shared_types.metadata_registry cimport MetadataRegistry, GLOBAL_METADATA_REGISTRY
# @formatter:on


cdef class ListMetadata:
    """
    Metadata storage backed by a Python list.

    Keys are mapped to integer slots via GLOBAL_METADATA_REGISTRY.
    """
    def __cinit__(self):
        self._values = []

    # ------------------------------------------------------------------
    # Retrieve metadata (fast path)
    # ------------------------------------------------------------------
    cpdef object get(self, str key, object default=None):
        cdef int idx = GLOBAL_METADATA_REGISTRY.ensure_index(key)
        cdef int n = len(self._values)
        cdef object v

        if idx < n:
            v = self._values[idx]
            if v is not None:
                return v
        return default

    # ------------------------------------------------------------------
    # Assign metadata value
    # ------------------------------------------------------------------
    cpdef void set(self, str key, object value):
        cdef int idx = GLOBAL_METADATA_REGISTRY.ensure_index(key)
        cdef int n = len(self._values)

        if idx >= n:
            self._values.extend([None] * (idx + 1 - n))

        self._values[idx] = value

    # Python dict-like syntax: obj[key] = value
    def __setitem__(self, key, value):
        self.set(<str> key, value)

    def __getitem__(self, key):
        return self.get(<str> key, None)

    # ------------------------------------------------------------------
    # Update from a dict
    # ------------------------------------------------------------------
    cpdef void update(self, dict mapping):
        cdef object k, v
        for k, v in mapping.items():
            self.set(<str> k, v)

    # ------------------------------------------------------------------
    # Check if key is present
    # ------------------------------------------------------------------
    cpdef bint contains(self, str key):
        cdef int idx = GLOBAL_METADATA_REGISTRY.find_index(key)
        if idx < 0 or idx >= len(self._values):
            return False
        return self._values[idx] is not None

    def __contains__(self, key):
        return self.contains(<str> key)

    # ------------------------------------------------------------------
    # Convert to regular Python dict (for JSON / DB)
    # ------------------------------------------------------------------
    cpdef dict to_dict(self):
        cdef dict out = {}
        cdef list vals = self._values
        cdef int n = len(vals)
        cdef int i
        cdef object v

        for i in range(n):
            v = vals[i]
            if v is not None:
                out[GLOBAL_METADATA_REGISTRY.key_for_index(i)] = v

        return out

    # Python iteration support
    def items(self):
        for key, value in self.to_dict().items():
            yield key, value

    def keys(self):
        for k in self.to_dict().keys():
            yield k

    def values(self):
        for v in self.to_dict().values():
            yield v
