import abc
from typing import Type


class Language:
    def uses_whitespace(self) -> bool:
        return True


_DEFAULT_LANGUAGE = Language()
_LANGUAGE_REGISTRY: dict[str, Language] = {}


def get_language(language: str) -> Language:
    return _LANGUAGE_REGISTRY.get(language, _DEFAULT_LANGUAGE)


def register_language(language: str):
    def wrapper(cls):
        if language in _LANGUAGE_REGISTRY:
            raise KeyError(f"Language '{language}' is already registered!")

        _LANGUAGE_REGISTRY[language] = cls()
        return cls

    return wrapper
