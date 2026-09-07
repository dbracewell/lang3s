from contextlib import contextmanager
from typing import Callable, Iterator


@contextmanager
def try_catch(
    on_error: Callable[[Exception], None] | None = None,
    raise_exception: bool = False,
    handled_exceptions: type[Exception] | tuple[type[Exception], ...] = (Exception,),
) -> Iterator[None]:
    if not isinstance(handled_exceptions, tuple):
        handled_exceptions = (handled_exceptions,)

    try:
        yield
    except handled_exceptions as e:
        if on_error:
            on_error(e)
        if raise_exception:
            raise
