import enum


class Metadata(str, enum.Enum):
    LANGUAGE = "language"
    MIME_TYPE = "mime-type"
    PATH = "path"
    LEMMA = "lemma"
    IS_STOPWORD = "is_stopword"
    START_CHAR = "start_char"
    END_CHAR = "end_char"
    HEAD = "head"
    RELATION = "relation"


class AnnotationTypes(str, enum.Enum):
    TOKEN = "token"
    SENTENCE = "sentence"
    ENTITY = "entity"
    PHRASE_CHUNK = "phrase_chunk"
    NOUN_CHUNK = "noun_chunk"
