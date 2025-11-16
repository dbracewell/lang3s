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
    WEIGHT = "weight"
    COREF = "coref"
    A0 = "A0"
    A0_TEXT = "A0_TEXT"
    A1 = "A1"
    A1_TEXT = "A1_TEXT"
    TIME = "TIME"
    TIME_TEXT = "TIME_TEXT"
    LOC = "LOC"
    LOC_TEXT = "LOC_TEXT"
    SOURCE = "source"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value


class AnnotationTypes(str, enum.Enum):
    TOKEN = "token"
    SENTENCE = "sentence"
    ENTITY = "entity"
    PHRASE_CHUNK = "phrase_chunk"
    NOUN_CHUNK = "noun_chunk"
    EVENT = "event"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value
