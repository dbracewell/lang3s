from threading import RLock
from typing import Protocol


class ShutdownEvent(Protocol):
    def is_set(self) -> bool: ...

    def set(self) -> None: ...


class SingletonMeta(type):
    """
    A Thread-Safe Singleton Metaclass that gives each class its own lock.
    """

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls._instance = None
        cls._lock = RLock()

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
