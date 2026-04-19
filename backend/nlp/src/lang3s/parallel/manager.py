from lang3s.parallel.core import Engine
from lang3s.parallel.runners import (
    AsyncRunner,
    BaseRunner,
    MultiprocessRunner,
    SingleThreadedRunner,
    ThreadedRunner,
)


class TaskManager:
    """Factory and Context Manager for low-effort creation."""

    def __init__(
        self,
        engine: Engine,
        initializer=None,
        initargs=(),
        **kwargs,
    ):
        self._engine: Engine = engine
        all_kwargs = kwargs.copy()
        all_kwargs["initializer"] = initializer
        all_kwargs["initargs"] = initargs
        self._runner: BaseRunner = self._build_runner(**all_kwargs)

    def _build_runner(self, **kwargs):
        if self._engine == Engine.MULTIPROCESSING:
            return MultiprocessRunner(**kwargs)
        if self._engine == Engine.THREADING:
            return ThreadedRunner(**kwargs)
        if self._engine == Engine.ASYNC:
            return AsyncRunner(**kwargs)
        if self._engine == Engine.SYNC:
            return SingleThreadedRunner(**kwargs)
        raise NotImplementedError

    def __enter__(self):
        return self._runner

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._runner.shutdown()
