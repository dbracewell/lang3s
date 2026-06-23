from contextlib import contextmanager
from typing import Callable, Type


@contextmanager
def try_catch(
    on_error: Callable[[Exception], None] | None = None,
    raise_exception: bool = False,
    handled_exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    try:
        yield
    except handled_exceptions as e:
        if on_error:
            on_error(e)
        if raise_exception:
            raise e
