"""Tiny in-process TTL cache for read endpoints.

A cache hit skips the ~2.5s Athena round-trip entirely and returns the last
computed response object. The cache is per-Lambda-container memory (not shared
across concurrent containers), which is fine for slow-changing demo reads —
each warm container serves repeats instantly and independently revalidates
after the TTL.

TTL is controlled by API_CACHE_TTL_SECONDS (default 60; set 0 to disable).
Applied only to deterministic GET reads — never to writes, searches, or
report endpoints whose payloads are time-sensitive (e.g. presigned URLs).

functools.wraps preserves the wrapped function's signature so FastAPI still
resolves path/query params correctly (inspect.signature follows __wrapped__),
exactly like the existing @tracer.capture_method decorator does.
"""

import functools
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def ttl_cache(default_ttl: int = 60) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        store: dict[tuple, tuple[float, Any]] = {}

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                ttl = int(os.environ.get("API_CACHE_TTL_SECONDS", str(default_ttl)))
            except ValueError:
                ttl = default_ttl
            if ttl <= 0:
                return fn(*args, **kwargs)
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            cached = store.get(key)
            if cached is not None and now - cached[0] < ttl:
                return cached[1]
            result = fn(*args, **kwargs)
            store[key] = (now, result)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
