from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings

_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    limit = settings.auth_rate_limit_per_minute
    if limit <= 0:
        return
    client = request.client.host if request.client else "unknown"
    key = f"auth:{client}"
    now = time.monotonic()
    window = 60.0
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth attempts")
    bucket.append(now)
