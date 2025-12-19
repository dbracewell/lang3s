from threading import Lock
from typing import TypeVar, Dict, Any, Callable

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def singleton(cls: Callable[P, T]) -> Callable[P, T]:
    _instances: Dict[Any, T] = {}
    _lock = Lock()

    def get_instance(*args: P.args, **kwargs: P.kwargs) -> T:
        if cls not in _instances:
            with _lock:
                if cls not in _instances:
                    _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]

    return get_instance
