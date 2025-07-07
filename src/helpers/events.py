import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from src.helpers.logger import Logger

logger = Logger(__name__)


class ListenerEntry:
    def __init__(
        self,
        listener: Callable[..., None | Coroutine],
        once: bool = False,
        retry_attempts: int | None = None,
        retry_delay: float | None = None,
    ):
        self.listener = listener
        self.once = once
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

    def __repr__(self):
        return (
            f"<ListenerEntry {getattr(self.listener, '__name__', repr(self.listener))}>"
        )

    def __eq__(self, other):
        if isinstance(other, ListenerEntry):
            return self.listener == other.listener
        return False


class Events:
    def __init__(self, default_retry_attempts=3, default_retry_delay=1.0):
        self._events: dict[str, list[ListenerEntry]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._default_retry_attempts = default_retry_attempts
        self._default_retry_delay = default_retry_delay
        self._worker_task: asyncio.Task | None = None
        self._lock = threading.Lock()
        self._running = False

    def on(
        self,
        event: str,
        listener: Callable[..., None | Coroutine],
        *,
        once: bool = False,
        retry_attempts: int | None = None,
        retry_delay: float | None = None,
    ):
        entry = ListenerEntry(listener, once, retry_attempts, retry_delay)
        with self._lock:
            self._events.setdefault(event, []).append(entry)
            logger.info(
                "Listener %r added to event: %s (once=%r)", listener, event, once
            )

    def off(self, event: str, listener: Callable | None = None):
        with self._lock:
            if event in self._events:
                if listener:
                    self._events[event] = [
                        e for e in self._events[event] if e.listener != listener
                    ]
                else:
                    del self._events[event]

    async def emit(self, event: str, *args: Any, **kwargs: Any):
        """Push the event to the internal queue (non-blocking for caller)."""
        await self._queue.put((event, args, kwargs))
        logger.info("Event '%s' enqueued", event)

    async def _worker(self):
        logger.info("Event worker started")
        self._running = True
        while self._running:
            try:
                event, args, kwargs = await self._queue.get()
                await self._handle_event(event, *args, **kwargs)
            except asyncio.CancelledError:
                logger.info("Event worker cancelled")
                break
            except RuntimeError as e:
                logger.error("RuntimeError in event worker: %r", e)
            except (OSError, ValueError) as e:
                logger.exception("Unexpected exception in event worker: %r", e)

    async def _handle_event(self, event: str, *args: Any, **kwargs: Any):
        with self._lock:
            listeners = list(self._events.get(event, []))

        logger.info("Processing event '%s' with %d listener(s)", event, len(listeners))

        async def invoke(entry: ListenerEntry):
            attempts = entry.retry_attempts or self._default_retry_attempts
            delay = entry.retry_delay or self._default_retry_delay
            name = getattr(entry.listener, "__name__", repr(entry.listener))

            for attempt in range(1, attempts + 1):
                try:
                    logger.info(
                        "Invoking listener '%s' for event '%s' (attempt %d)",
                        name,
                        event,
                        attempt,
                    )
                    # Check if the listener is a coroutine function
                    if asyncio.iscoroutinefunction(entry.listener):
                        await entry.listener(*args, **kwargs)
                    else:
                        entry.listener(*args, **kwargs)
                    logger.info("Listener %s succeeded on attempt %d", name, attempt)
                    break
                except (TypeError, ValueError, RuntimeError) as e:
                    logger.error(
                        "Listener '%s' failed (attempt %d): %r", name, attempt, e
                    )
                    if attempt < attempts:
                        await asyncio.sleep(delay)
                    else:
                        logger.critical(
                            "Listener '%s' gave up after %d attempts", name, attempts
                        )

        await asyncio.gather(*(invoke(entry) for entry in listeners))

        with self._lock:
            if event in self._events:
                self._events[event] = [
                    entry for entry in self._events[event] if not entry.once
                ]

    async def start_worker(self):
        """Start background event processor (call once during app init)."""
        logger.info("Starting event worker")
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def stop_worker(self):
        """Stop the background event processor (clean shutdown)."""
        logger.info("Stopping event worker")
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                logger.info("Event worker stopped")


class _Events:
    _instance: Events | None = None

    @classmethod
    def get_instance(cls) -> Events:
        if cls._instance is None:
            logger.info("Creating global events singleton instance")
            cls._instance = Events()
        return cls._instance


# Global events instance
events: Events = _Events.get_instance()
