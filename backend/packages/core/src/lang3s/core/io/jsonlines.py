from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import jsonlines
from jsonlines import Writer


def jsonlines_reader(file: str | Path) -> Generator[Any, Any, Any]:
    with jsonlines.open(file, mode="r") as reader:
        for doc in reader:
            yield doc


@contextmanager
def jsonlines_writer(file: str | Path) -> Generator[Writer, Any, Any]:
    with jsonlines.open(file, mode="w") as writer:
        yield writer
