from threading import RLock


class SingletonMeta(type):
    """
    A Thread-Safe Singleton Metaclass that gives each class its own lock.
    """

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls._instance = None
        cls._lock = RLock()  # RLock allows the same thread to acquire it multiple times

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Create the instance
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
