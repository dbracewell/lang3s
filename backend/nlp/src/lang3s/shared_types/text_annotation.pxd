# text_annotation.pxd
from .text_object cimport TextObject
from .text cimport Text

cdef class TextAnnotation(TextObject):
    cdef object _owner_ref
    cdef str type
    cdef readonly int sentence_id
    cdef str value
    cdef readonly int _start
    cdef readonly int _end
    cdef str source

    cdef object get_parent(self)
    cdef list get_subtree(self)
    cdef list get_children(self)
    cdef object get_coref(self)
    cpdef void detach(self)