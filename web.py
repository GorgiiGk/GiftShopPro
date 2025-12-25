import os
from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

from db import (
    init_db,
    list_products,
    get_product,
    get_or_create_user,
    list_orders_for_user,
)

# ✅ Загружаем .env (чтобы в PythonAnywhere заработало)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_WEBAPP_URL = os.getenv("PUBLIC_WEBAPP_URL", "")
DB_PATH = os.getenv("DB_PATH", "/home/GiftUpR0bot/GiftShopPro/shop.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing (create .env and put BOT_TOKEN=...)")

app = FastAPI(title="GiftShopPro Web")


# -------------------------
# Helpers (пример)
# -------------------------
def validate_init(initData: str):
    """
    Тут должна быть твоя функция валидации Telegram WebApp initData.
    Пока что сделаем заглушку, чтобы API хотя бы запускался.
    """
    if not initData:
        raise Exception("initData is empty")
    # Если у тебя уже есть нормальная validate_init — вставь её сюда
    return (123, "Test", "testuser")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/products")
def products(initData: str):
    try:
        validate_init(initData)
    except Exception:
        raise HTTPException(401, "Unauthorized")

    ps = list_products(True)
    return [{
        "id": p["id"],
        "title": p["title"],
        "description": p["description"],
        "price_provider": p["price_provider"],
        "currency_provider": p["currency_provider"],
        "price_stars": p["price_stars"],
        "image_url": p["image_url"],
    } for p in ps]


@app.get("/api/me/orders")
def my_orders(initData: str):
    try:
        tg_user_id, first_name, username = validate_init(initData)
    except Exception:
        raise HTTPException(401, "Unauthorized")

    get_or_create_user(tg_user_id, first_name, username)
    os_ = list_orders_for_user(tg_user_id, 50)

    return [{
        "id": o["id"],
        "status": o["status"],
        "currency": o["currency"],
        "amount": o["amount"],
        "gift_delivered": bool(o["gift_delivered"]),
        "delivered_code": o["delivered_code"],
    } for o in os_]


@app.post("/api/orders")
async def make_order(req: Request, initData: str):
    # На PythonAnywhere мы НЕ делаем invoice из WebApp.
    # Это лучше делать через бота.
    raise HTTPException(400, "Invoice must be initiated by bot.")


@app.on_event("startup")
async def _startup():
    init_db()
