from lingua import Language, LanguageDetectorBuilder

_detection_languages = [
    Language.ENGLISH,
    Language.JAPANESE,
    Language.SPANISH,
    Language.GERMAN,
    Language.FRENCH,
    Language.DUTCH,
    Language.CHINESE,
]
_detector = LanguageDetectorBuilder.from_languages(*_detection_languages).build()


def detect_language(text: str) -> str:
    lang = _detector.detect_language_of(text)
    if lang is None:
        return "en"
    return str(lang.iso_code_639_1.name).lower()
