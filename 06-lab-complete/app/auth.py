"""Authenticate requests with the configured API key."""
from hmac import compare_digest

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Security(api_key_header)) -> str:
    if not key or not settings.agent_api_key or not compare_digest(
        key.encode(), settings.agent_api_key.encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return key
