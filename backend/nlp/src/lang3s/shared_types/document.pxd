# document.pxd
from .list_metadata cimport ListMetadata
from .text cimport Text

cdef class Document:
    cdef readonly str id
    cdef readonly str title
    cdef readonly Text text
    cdef ListMetadata _meta

    cpdef dict to_json(self)
    cpdef list insert_values(self)
