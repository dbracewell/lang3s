# # distutils: language = c++
# import itertools
# from typing import (
#     Any,
#     Dict,
#     List,
#     Optional,
#     Tuple,  # type: ignore
# )
#
# import numpy as np
# import shortuuid
# from more_itertools.more import first
# from numpy.typing import NDArray
# from psycopg.types.json import Jsonb
#
# from . import Metadata
# from .metadata import AnnotationTypes
#
# # cython: language_level=3
# cdef class MetadataRegistry:
#     cdef dict _key2id
#     cdef list _id2key
#
#     def __cinit__(self):
#         self._key2id = {}
#         self._id2key = []
#
#     cpdef int size(self):
#         return len(self._id2key)
#
#     cpdef int get_id(self, str key):
#         return self._key2id.get(key, -1)
#
#     cpdef int get_key(self, int id):
#         return self._key2id.get(id, -1)
#
#     cpdef int ensure(self, str key):
#         cdef int idx = self._key2id.get(key, -1)
#         if idx >= 0:
#             return idx
#         idx = len(self._id2key)
#         self._id2key.append(key)
#         self._key2id[key] = idx
#         return idx
#
# cdef MetadataRegistry GLOBAL_REGISTRY = MetadataRegistry()
#
# cdef tuple start_end_key(a):
#     return a.start, a.end
#
# cdef class TextObject:
#     cdef object embedding
#     cdef readonly str id
#     cdef readonly str doc_id
#     cdef readonly str text
#     cdef list _meta
#
#     def __init__(self, str id, str doc_id, str text, object embedding):
#         self.id = id
#         self.doc_id = doc_id
#         self.text = text
#         self.embedding = embedding
#         self._meta = []
#
#     cpdef str to_string(self,
#                         bint ignore_stopwords=False,
#                         bint lemmatize=False,
#                         bint lowercase=False):
#         """
#         Convert tokens to a string with optional filtering/processing.
#         Optimized for Cython speed by minimizing repeated attribute lookups.
#         """
#         cdef list out = []
#         cdef object token
#         cdef str token_str
#         cdef object tokens = self.tokens  # avoid repeated attribute lookups
#         cdef object lemma_key
#
#         for token in tokens:
#             token_str = token.text
#             if ignore_stopwords and token.is_stopword:
#                 continue
#             if lemmatize:
#                 token_str = token.lemma
#             if lowercase:
#                 token_str = token_str.lower()
#             out.append(token_str)
#         return " ".join(out)
#
#     cpdef list interleave(self, str interleaved):
#         cdef list items = []
#         cdef list annotations = self.annotations_of_type(interleaved)  #type:ignore
#         cdef list tokens
#         cdef Py_ssize_t ti = 0
#         cdef Py_ssize_t ai = 0
#         cdef Py_ssize_t nt, na
#         cdef object token, ann
#
#         if len(annotations) == 0:
#             return self.tokens
#
#         annotations = sorted(annotations, key=start_end_key)
#         tokens = sorted(self.tokens, key=start_end_key)
#
#         na = len(annotations)
#         nt = len(tokens)
#
#         while ti < nt or ai < na:
#             if ai >= na:
#                 items.extend(tokens[ti:])
#                 break
#
#             token = tokens[ti]
#             ann = annotations[ai]
#
#             if ann.start <= token.start:
#                 items.append(ann)
#                 ai += 1
#
#                 while ti < nt and tokens[ti].start < ann.end:
#                     ti += 1
#             else:
#                 items.append(token)
#                 ti += 1
#
#         return items
#
#     cdef bint _is_stopword(self):
#         stopword = self[Metadata.IS_STOPWORD.value]
#         if stopword:
#             return stopword
#
#         cdef list tokens = self.tokens
#         for token in tokens:  #type: ignore
#             if token[Metadata.IS_STOPWORD.value] is False:
#                 return False
#         return True
#
#     @property
#     def is_stopword(self) -> bool:
#         return self._is_stopword()  #type: ignore
#
#     @property
#     def start(self) -> int:
#         """Return start position as int"""
#         raise NotImplementedError()
#
#     @property
#     def end(self) -> int:
#         """Return end position as int"""
#         raise NotImplementedError()
#
#     @property
#     def lemma(self) -> str:
#         lemma_text = self[Metadata.LEMMA.value]
#         if lemma_text is None:
#             return " ".join([token.lemma for token in self.tokens])
#         return lemma_text
#
#     @property
#     def sentences(self) -> List["TextAnnotation"]:
#         raise NotImplementedError()
#
#     @property
#     def tokens(self) -> List["TextAnnotation"]:
#         raise NotImplementedError()
#
#     @property
#     def entities(self) -> List["TextAnnotation"]:
#         return self.annotations_of_type(AnnotationTypes.ENTITY.value)
#
#     @property
#     def noun_chunks(self) -> List["TextAnnotation"]:
#         return self.annotations_of_type(AnnotationTypes.NOUN_CHUNK.value)
#
#     @property
#     def owner(self) -> "Text":
#         raise NotImplementedError()
#
#     # @property
#     # def events(self) -> List["Event"]:
#     #     event_list = []
#     #     for trigger in self.annotations_of_type(AnnotationTypes.EVENT.value):
#     #         A0 = trigger["A0"]
#     #         if A0 is None:
#     #             A0 = []
#     #         A1 = trigger["A1"]
#     #         if A1 is None:
#     #             A1 = []
#     #
#     #         LOC = self.owner.get_annotation(trigger["LOC"])
#     #         TIME = self.owner.get_annotation(trigger["TIME"])
#     #         event_list.append(
#     #             Event(
#     #                 trigger=trigger,
#     #                 value=trigger.value,
#     #                 A0=filter_none(
#     #                     self.owner.get_annotation(aid) for aid in A0
#     #                 ),
#     #                 A1=filter_none(
#     #                     self.owner.get_annotation(aid) for aid in A1
#     #                 ),
#     #                 TIME=TIME,
#     #                 LOC=LOC,
#     #             )
#     #         )
#     #     return event_list
#
#     def overlaps(self, TextObject other) -> bool:
#         if self.doc_id != other.doc_id:
#             return False
#         return self.start < other.end and self.end > other.start  #type: ignore
#
#     def annotations_of_type(self, type: str) -> List["TextAnnotation"]:
#         raise NotImplementedError()
#
#     cpdef object get(self, str key):
#         cdef int slot = GLOBAL_REGISTRY.get_id(key)
#         if slot < 0:
#             return None
#         if slot >= len(self._meta):
#             return None
#         return self._meta[slot]
#
#     cpdef void set(self, str key, object value):
#         cdef int slot = GLOBAL_REGISTRY.ensure(key)
#         cdef int needed = slot + 1 - len(self._meta)
#         if needed > 0:
#             self._meta.extend([None] * needed)
#         self._meta[slot] = value
#
#     def __getitem__(self, key: str):
#         return self.get(key)  #type: ignore
#
#     def __setitem__(self, key: str, value):
#         self.set(key, value)  #type: ignore
#
#     def __str__(self):
#         return self.text
#
#     def __repr__(self):
#         return self.text
#
# cdef metadata_to_dict(list meta):
#     cdef metadata = {}
#     for i in range(len(meta)):
#         value = meta[i]
#         if value is None:
#             metadata[GLOBAL_REGISTRY.get_key(i)] = meta[i]
#     return metadata
#
# cdef class TextAnnotation(TextObject):
#     cdef readonly int _start
#     cdef readonly int _end
#     cdef readonly str type
#     cdef readonly str value
#     cdef readonly object _owner
#     cdef readonly int sentence_id
#
#     DB_COLUMNS = [
#         "id",
#         "text_id",
#         "doc_id",
#         "start",
#         "end",
#         "sentence_id",
#         "type",
#         "value",
#         "text",
#         "clean_text",
#         "mapping",
#         "embedding",
#         "full_embedding",
#         "metadata",
#     ]
#
#     def __init__(
#         self,
#         id: str,
#         owner: "Text",
#         text: str,
#         start: int,
#         end: int,
#         sentence_id: int,
#         type: str,
#         value: str,
#         embedding: Optional[NDArray[np.floating]] = None,
#         metadata: Dict[str, str] | None = None,
#     ):
#         super().__init__(id=id,
#                          doc_id=owner.doc_id,
#                          text=text,
#                          embedding=embedding or np.zeros(1))  #type: ignore
#         self._start = start
#         self._end = end
#         self.type = type
#         self._owner = owner
#         self.sentence_id = sentence_id
#         self.value = value
#         if metadata is not None:
#             for k, v in metadata.items():
#                 self[k] = v
#
#     cdef list _subtree(self):
#         cdef set visited = set()  # memory-efficient
#         cdef list horizon = [self]  # BFS stack/queue
#         cdef list ancestors = []
#         cdef object n
#         cdef int s
#         cdef list children
#         cdef object child
#
#         while horizon:
#             n = horizon.pop()
#             s = n.start
#             if s not in visited:
#                 visited.add(s)
#                 children = n.children
#                 for child in children:
#                     horizon.append(child)
#                     ancestors.append(child)
#
#         return ancestors
#
#     cdef _children(self):
#         cdef list children = []
#         cdef list owner_tokens = self._owner.tokens
#         if self.type == "token":
#             for token in owner_tokens:  #type: ignore
#                 if token[Metadata.HEAD.value] == self._start:
#                     children.append(token)
#             return children
#
#         tokens = self.tokens
#         for token in tokens:
#             children.extend(token.children)
#         return children
#
#     cdef object _parent(self):
#         cdef object head
#         cdef set span_set
#         cdef object token
#
#         """
#         Returns the parent TextAnnotation of this token/span.
#         """
#
#         if self.type == "token":
#             head = self.get(Metadata.HEAD.value)  #type:ignore
#             if head == self.start:
#                 return None
#             return self._owner.tokens[head]
#
#         # For spans
#         span_set = set(token.start for token in self.tokens)
#
#         for token in self.tokens:
#             head = token.get(Metadata.HEAD.value)  #type:ignore
#             if head not in span_set or head == token.start:
#                 return self._owner.tokens[head]
#
#         return None
#
#     @property
#     def parent(self) -> Optional["TextAnnotation"]:
#         return self._parent()
#
#     def __eq__(self, other):
#         if not isinstance(other, TextAnnotation):  #type: ignore
#             return NotImplemented
#         return self.id == other.id
#
#     def __hash__(self):
#         return hash(self.id)
#
#     @property
#     def subtree(self) -> List["TextAnnotation"]:
#         return self._subtree()  #type: ignore
#
#     @property
#     def children(self) -> List["TextAnnotation"]:
#         return self._children()  #type: ignore
#
#     @property
#     def coref(self) -> "TextAnnotation":
#         coref_id = self.get("coref")  #type: ignore
#         if coref_id is None:
#             return self
#         return first(
#             filter(lambda x: x.id == coref_id, self._owner.annotations), self
#         )
#
#     @property
#     def start(self) -> int:
#         return self._start
#
#     @property
#     def end(self) -> int:
#         return self._end
#
#     @property
#     def owner(self) -> "Text":
#         return self._owner
#
#     def insert_values(self):
#         return [
#             self.id,
#             self._owner.id,
#             self._owner.doc_id,
#             self._start,
#             self._end,
#             self.sentence_id,
#             self.type,
#             self.value,
#             self.text,
#             self.to_string(True, True, True),
#             f"{self.type}:{self.value}"
#             if self.type not in ["sentence", "noun_chunk"]
#             else None,
#             "".join(
#                 (str(i) for i in (self.embedding > 0).astype(int).tolist())
#             ),
#             self.embedding,
#             Jsonb({GLOBAL_REGISTRY.get_key(i): self._meta[i] for i in range(len(self._meta)) if
#                    self._meta[i] is not None}),
#         ]
#
#     @property
#     def dep(self):
#         if self.type == "token":
#             return self[Metadata.RELATION.value]
#         parent = self.parent
#         if parent is None:
#             return "ROOT"
#         return parent[Metadata.RELATION.value]
#
#     @property
#     def tokens(self) -> List["TextAnnotation"]:
#         if self.type == "token":
#             return [self]
#         return [a for a in self._owner.tokens[self.start: self.end]]
#
#     def annotations_of_type(self, type: str) -> List["TextAnnotation"]:
#         return [
#             a
#             for a in self._owner.annotations
#             if a.type == type and self.overlaps(a)
#         ]
#
#     @property
#     def sentence(self) -> "TextAnnotation":
#         for s in self._owner.sentences:
#             if s.start < self.end and s.end > self.start:
#                 return s
#         raise Exception("No sentence found")
#
#     @property
#     def sentences(self) -> List["TextAnnotation"]:
#         return [self.sentence]
#
#     def to_json(self) -> Dict[str, Any]:
#         return {
#             "id": self.id,
#             "text": self.text,
#             "start": self.start,
#             "end": self.end,
#             "type": self.type,
#             "value": self.value,
#             "sentence_id": self.sentence_id,
#             "embedding": self.embedding.tolist(),
#             "metadata": {GLOBAL_REGISTRY.get_key(i): self._meta[i] for i in range(len(self._meta)) if
#                          self._meta[i] is not None}
#         }
#
# cdef class Text(TextObject):
#     DB_COLUMNS = [
#         "id",
#         "text",
#         "doc_id",
#         "embedding",
#         "full_embedding",
#         "metadata",
#     ]
#     cdef list _annotations
#     cdef list _tokens
#     cdef list _sentences
#
#     def __init__(
#         self,
#         doc_id: str,
#         content: str,
#         id: Optional[str] = None,
#         metadata: Optional[Dict[str, Any]] = None,
#         embedding: Optional[NDArray[np.floating]] = None,
#     ):
#         super().__init__(id=id or shortuuid.uuid(),
#                          doc_id=doc_id,
#                          text=content,
#                          embedding=embedding if embedding is not None else np.zeros(0))
#         self._annotations = []
#         self._tokens = []
#         self._sentences = []
#         if metadata is not None:
#             for k, v in metadata.items():
#                 self[k] = v
#
#     def get_annotation(self, id: Optional[str]) -> Optional[TextAnnotation]:
#         if id is None:
#             return None
#         return first(filter(lambda a: a.id == id, self.all_annotations), None)
#
#     @property
#     def sentences(self) -> List["TextAnnotation"]:
#         return self._sentences
#
#     @property
#     def tokens(self) -> List["TextAnnotation"]:
#         return self._tokens
#
#     @property
#     def is_stopword(self) -> bool:
#         return False
#
#     @property
#     def all_annotations(self):
#         return list(
#             itertools.chain.from_iterable(
#                 [self.tokens, self.sentences, self.annotations]
#             )
#         )
#
#     def tag_data(
#         self,
#     ) -> Tuple[
#         List[TextAnnotation], List[List[TextAnnotation]], List[List[str]]
#     ]:
#         tokens = []
#         sentences = []
#         token_strs = []
#         for sentence in self.sentences:
#             sentences.append(sentence)
#             tokens.append(sentence.tokens)
#             token_strs.append([token.text for token in sentence.tokens])
#         return sentences, tokens, token_strs
#
#     @property
#     def owner(self) -> "Text":
#         return self
#
#     @property
#     def start(self):
#         return self.tokens[0].start
#
#     @property
#     def end(self):
#         return self.tokens[-1].end
#
#     def insert_values(self):
#         return [
#             self.id,
#             self.text,
#             self.doc_id,
#             "".join(
#                 (str(i) for i in (self.embedding > 0).astype(int).tolist())
#             ),
#             self.embedding,
#             Jsonb({GLOBAL_REGISTRY.get_key(i): self._meta[i] for i in range(len(self._meta)) if
#                    self._meta[i] is not None}),
#         ]
#
#     cpdef list _annotations_of_type(self, str annotation_type):
#         cdef list annotations = []
#         for a in self._annotations:
#             if a.type == annotation_type:
#                 annotations.append(a)
#         return annotations
#
#     def annotations_of_type(self, type: str) -> List["TextAnnotation"]:
#         return self._annotations_of_type(type)  #type: ignore
#
#     def to_json(self):
#         return {
#             "id": self.id,
#             "text": self.text,
#             "embedding": self.embedding.tolist(),
#             "metadata": metadata_to_dict(self._meta),  #type:ignore
#             "annotations": list(
#                 a.to_json()
#                 for a in itertools.chain.from_iterable(
#                     [self.tokens, self.sentences, self._annotations]
#                 )
#             ),
#         }
#
#     # @staticmethod
#     # def from_json(obj: Dict[str, Any]) -> "Text":
#     #     text_dict = obj["text"]
#     #
#     #     embedding = text_dict["embedding"]
#     #     if isinstance(embedding, str):
#     #         embedding = np.array(json.loads(embedding))
#     #     if isinstance(embedding, list):
#     #         embedding = np.array(embedding)
#     #
#     #     text = Text(
#     #         id=text_dict["id"],
#     #         metadata=text_dict.get("metadata", {}),
#     #         content=text_dict["text"],
#     #         doc_id=obj["id"],
#     #         embedding=embedding,
#     #     )
#     #
#     #     for annotation in text_dict["annotations"]:
#     #         embedding = annotation["embedding"]
#     #         if embedding is not None:
#     #             if isinstance(embedding, str):
#     #                 embedding = np.array(
#     #                     json.loads(embedding), dtype=np.float16
#     #                 )
#     #             if isinstance(embedding, list):
#     #                 embedding = np.array(embedding, dtype=np.float16)
#     #         text.add_annotation(
#     #             id=annotation["id"],
#     #             text=annotation["text"],
#     #             start=annotation["start"],
#     #             end=annotation["end"],
#     #             sentence_id=annotation["sentence_id"],
#     #             type=annotation["type"],
#     #             value=annotation["value"],
#     #             embedding=embedding,
#     #             metadata=annotation.get("metadata", {}),
#     #         )
#     #     text._tokens = sorted(text.tokens, key=lambda token: token.start)
#     #     text._sentences = sorted(
#     #         text.sentences, key=lambda sentences: sentences.start
#     #     )
#     #     return text
#
#     def add_annotation(
#         self,
#         text: str,
#         start: int,
#         end: int,
#         sentence_id: int,
#         type: str,
#         value: str,
#         id: Optional[str] = None,
#         embedding: Optional[NDArray[np.floating]] = None,
#         metadata: Dict[str, Any] | None = None,
#     ) -> TextAnnotation:
#         annotation = TextAnnotation(
#             id=id if id is not None else shortuuid.uuid(),
#             owner=self,
#             text=text,
#             start=start,
#             end=end,
#             sentence_id=sentence_id,
#             type=type,
#             value=value,
#             embedding=embedding,
#             metadata=metadata,
#         )
#         if annotation.type == AnnotationTypes.TOKEN.value:
#             self._tokens.append(annotation)
#         elif annotation.type == AnnotationTypes.SENTENCE.value:
#             self._sentences.append(annotation)
#         else:
#             self._annotations.append(annotation)
#         return annotation
#
#     # def attach_annotation(self, annotation: TextAnnotation):
#     #     if self.get_annotation(annotation.id) is not None:
#     #         return
#     #     if annotation.type == AnnotationTypes.TOKEN.value:
#     #         self.tokens.append(annotation)
#     #     elif annotation.type == AnnotationTypes.SENTENCE.value:
#     #         self.sentences.append(annotation)
#     #     else:
#     #         self.annotations.append(annotation)
#     #     return annotation
#
#     def create_span(
#         self,
#         start: int,
#         end: int,
#         type: Optional[str] = None,
#         value: Optional[str] = None,
#         metadata: Optional[Dict[str, Any]] = None,
#     ) -> TextAnnotation:
#         annotation = TextAnnotation(
#             id=shortuuid.uuid(),
#             owner=self,
#             text=" ".join([t.text for t in self.tokens[start:end]]),
#             start=start,
#             end=end,
#             sentence_id=min((t.sentence_id for t in self.tokens[start:end])),
#             type=type or "span",
#             value=value or "",
#             metadata=metadata,
#         )
#         return annotation
