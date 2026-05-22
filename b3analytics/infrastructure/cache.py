import functools
import time

_store: dict = {}


def ttl_cache(seconds: int = 300):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            cached = _store.get(key)
            if cached and time.time() - cached["ts"] < seconds:
                return cached["value"]
            result = fn(*args, **kwargs)
            _store[key] = {"value": result, "ts": time.time()}
            return result
        return wrapper
    return decorator
