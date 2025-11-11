from threading import Lock
from typing import Any, Callable, Dict, Type, TypeVar, cast

T = TypeVar("T")


def singleton(cls: Type[T]) -> Callable[..., T]:
    _instances: Dict[Type[T], T] = {}
    _lock = Lock()

    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in _instances:
            with _lock:
                # Double-checked locking
                if cls not in _instances:
                    _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]

    return cast(Callable[..., T], get_instance)
