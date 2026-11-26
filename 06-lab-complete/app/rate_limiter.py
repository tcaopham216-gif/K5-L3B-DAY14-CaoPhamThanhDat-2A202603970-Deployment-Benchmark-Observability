"""Enforce a shared sliding window per API key."""
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Redis runs the entire update atomically and supplies a common clock for all workers.
take_slot = r.register_script("""
local time = redis.call('TIME')
local now = time[1] * 1000 + math.floor(time[2] / 1000)
local key = KEYS[1]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - 60000)
if tonumber(ARGV[1]) <= 0 then
    return 60
end
if redis.call('ZCARD', key) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return math.ceil((tonumber(oldest[2]) + 60000 - now) / 1000)
end
redis.call('ZADD', key, now, ARGV[2])
redis.call('PEXPIRE', key, 60000)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_hash = sha256(key.encode()).hexdigest()
    retry_after = take_slot(
        keys=[f"lab14:rate:{key_hash}"],
        args=[settings.rate_limit_per_minute, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
