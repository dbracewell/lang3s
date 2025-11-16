# text.pxd

from .text_object cimport TextObject

cdef class Text(TextObject):
    cdef list _annotations
    cdef list _tokens
    cdef list _sentences

    cpdef object get_annotation(self, str id)

    cpdef void remove_annotations(self, list sources)
