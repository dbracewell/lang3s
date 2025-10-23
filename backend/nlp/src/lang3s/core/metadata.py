import enum


class Metadata(str, enum.Enum):
    LANGUAGE = "language"
    MIME_TYPE = "mime-type"
    PATH = "path"


class AnnotationTypes(str, enum.Enum):
    TOKEN = "token"
    SENTENCE = "sentence"
    ENTITY = "entity"
    PHRASE_CHUNK = "phrase_chunk"
    NOUN_CHUNK = "noun_chunk"
