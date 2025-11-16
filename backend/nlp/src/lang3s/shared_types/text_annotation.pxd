# text_annotation.pxd
from .text_object cimport TextObject
from .text cimport Text

cdef class TextAnnotation(TextObject):
    cdef readonly Text _owner
    cdef str type
    cdef readonly int sentence_id
    cdef str value
    cdef readonly int _start
    cdef readonly int _end
    cdef str source

    cdef  get_parent(self)
    cdef list get_subtree(self)
    cdef list get_children(self)
    cdef object get_coref(self)
