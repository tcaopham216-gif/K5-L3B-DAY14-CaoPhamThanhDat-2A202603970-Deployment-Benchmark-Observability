"""Production agent with Redis-backed request and spending limits."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger("lab14.agent")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.propagate = False


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": "INFO",
        "event": event,
        "environment": settings.environment,
        **fields,
    }))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup")
    try:
        yield
    finally:
        # Uvicorn drains in-flight requests before invoking lifespan shutdown.
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event(
            "request",
            method=request.method,
            path=request.url.path,
            status=status,
            ms=round((perf_counter() - started) * 1000, 2),
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    day = datetime.now(timezone.utc)
    try:
        check_rate_limit(key)
        check_budget(day)
        answer = llm_ask(body.question)
        cost = record_cost(day, max(1, len(body.question) // 4), max(1, len(answer) // 4))
    except RedisError:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"question": body.question, "answer": answer, "cost_usd": cost}
