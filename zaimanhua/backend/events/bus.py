from __future__ import annotations

import queue
import threading
from typing import Any


class EventBus:
    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: set[queue.Queue] = set()
        self._closed = False

    def subscribe(self, maxsize: int = 0) -> queue.Queue:
        subscriber = queue.Queue(maxsize=maxsize)
        with self._lock:
            if self._closed:
                return subscriber
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._subscribers.clear()

    @staticmethod
    def _offer(subscriber: queue.Queue, event: dict[str, Any]) -> None:
        try:
            subscriber.put_nowait(event)
            return
        except queue.Full:
            pass
        try:
            subscriber.get_nowait()
        except queue.Empty:
            return
        try:
            subscriber.put_nowait(event)
        except queue.Full:
            return

    def publish(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        with self._lock:
            if self._closed:
                return
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            self._offer(subscriber, dict(event))
