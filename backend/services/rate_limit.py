"""
Simple in-memory sliding-window rate limiter.

Suitable for a single-process deployment. For multi-worker / multi-instance
setups this should be backed by Redis, but it keeps the dependency surface
small for now.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from services.auth_middleware import get_current_user

# user_id -> deque of request timestamps (monotonic seconds)
_HITS: dict[str, deque[float]] = defaultdict(deque)


def _check(user_id: str, max_requests: int, window_seconds: int) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    bucket = _HITS[user_id]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_requests:
        retry_in = int(bucket[0] + window_seconds - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit reached ({max_requests}/hour). Try again in ~{max(retry_in, 1)}s.",
            headers={"Retry-After": str(max(retry_in, 1))},
        )
    bucket.append(now)


def rate_limit(max_requests: int = 10, window_seconds: int = 3600):
    """FastAPI dependency factory enforcing a per-user request budget."""

    async def dependency(user: dict = Depends(get_current_user)) -> dict:
        _check(user["id"], max_requests, window_seconds)
        return user

    return dependency
