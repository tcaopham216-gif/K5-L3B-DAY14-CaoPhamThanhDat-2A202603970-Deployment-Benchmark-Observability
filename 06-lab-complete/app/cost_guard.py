"""Track estimated LLM spend in a shared daily USD budget."""
from datetime import datetime

from fastapi import HTTPException

from .config import settings
from .redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def check_budget(day: datetime) -> None:
    budget_key = f"lab14:cost:{day.date().isoformat()}"
    if float(r.get(budget_key) or 0) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exhausted")


def record_cost(day: datetime, input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    budget_key = f"lab14:cost:{day.date().isoformat()}"
    with r.pipeline() as transaction:
        transaction.incrbyfloat(budget_key, cost)
        transaction.expire(budget_key, 172800)
        transaction.execute()
    return cost
