# metadata_registry.pxd

cdef class MetadataRegistry:
    # C-layout must be declared here
    cdef dict _key_to_index
    cdef list _index_to_key
    cdef object _lock  # RLock

    # Methods visible to other Cython features
    cpdef int ensure_index(self, str key)
    cpdef int find_index(self, str key)
    cpdef str key_for_index(self, int idx)

cdef MetadataRegistry GLOBAL_METADATA_REGISTRY
