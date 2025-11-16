# list_metadata.pxd

from lang3s.shared_types.metadata_registry cimport MetadataRegistry, GLOBAL_METADATA_REGISTRY

cdef class ListMetadata:
    cdef list _values

    cpdef object get(self, str key, object default=?)
    cpdef void set(self, str key, object value)
    cpdef dict to_dict(self)
    cpdef void update(self, dict mapping)
    cpdef bint contains(self, str key)
