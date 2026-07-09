from contextlib import contextmanager
from os import PathLike
from typing import Any, Generator

import jsonlines
from jsonlines import Writer


def jsonlines_reader(file: str | PathLike) -> Generator[Any, Any, Any]:
    with jsonlines.open(file, mode="r") as reader:
        for doc in reader:
            yield doc


@contextmanager
def jsonlines_writer(file: str | PathLike) -> Generator[Writer, Any, Any]:
    with jsonlines.open(file, mode="w") as writer:
        yield writer
