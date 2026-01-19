# text_object.pxd

from .list_metadata cimport ListMetadata  # your cython ListMetadata

cdef class TextObject:
    cdef readonly str id
    cdef readonly str doc_id
    cdef readonly str text

    cdef object  _embedding
    cdef ListMetadata _meta

    cpdef object get(self, str metadata_key, object default_value= *)

    cdef object get_embedding(self)
    cdef set_embedding(self, object value)

    cdef int get_start(self)
    cdef int get_end(self)

    cdef list get_sentences(self)
    cdef list get_tokens(self)

    cdef int get_end(self)
    cdef int get_start(self)

    cdef bint _is_stopword(self)
    cdef str get_lemma(self)
    cdef object get_owner(self)

    cdef list get_events(self)

    cpdef list annotations_of_type(self, str t)
    cpdef list interleave(self, str annotation_type)
    cpdef bint overlaps(self, TextObject other)
    cpdef str to_string(self, bint ignore_stopwords, bint lemmatize, bint lowercase)
