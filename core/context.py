"""
Project Context

Thread-safe shared memory for all agents working on the same project.
"""

from threading import RLock


class ProjectContext:

    def __init__(self):
        self.data = {}
        self._lock = RLock()

    def save(self, key, value):
        with self._lock:
            self.data[key] = value

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def all(self):
        with self._lock:
            return dict(self.data)
