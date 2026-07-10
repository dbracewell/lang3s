import threading


class ThreadSafeCounter:
    def __init__(self, initial_value=0):
        self._value = initial_value
        self._lock = threading.Lock()

    def increment(self, amount=1):
        """Safely increment the counter."""
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount=1):
        """Safely decrement the counter."""
        with self._lock:
            self._value -= amount
            return self._value

    @property
    def value(self):
        """Safely read the current value."""
        with self._lock:
            return self._value
