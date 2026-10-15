import random

from fastapi import FastAPI, HTTPException, Response

app = FastAPI(title="Northwind Mock API")


@app.get("/accounts/{account_id}")
async def get_account(account_id: str, response: Response):
    # Имитируем ограничение частоты запросов внешним API.
    if random.random() < 0.2:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "2"},
        )

    return {
        "id": account_id,
        "name": f"Northwind Account {account_id}",
        "status": "active",
    }
