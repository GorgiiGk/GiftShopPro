import os
from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

from db import (
    init_db,
    list_products,
    get_product,
    get_or_create_user,
    list_orders_for_user,
    create_order,
)

# Загружаем .env (чтобы работало и в PythonAnywhere)
load_dotenv("/home/GiftUpR0bot/GiftShopPro/.env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_WEBAPP_URL = os.getenv("PUBLIC_WEBAPP_URL", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing (create .env and put BOT_TOKEN=...)")

app = FastAPI(title="GiftShopPro Web")


# -------------------------
# Telegram WebApp initData validation (ЗАГЛУШКА)
# -------------------------
def validate_init(initData: str):
    """
    Тут должна быть НОРМАЛЬНАЯ проверка initData (HMAC).
    Пока заглушка, чтобы API запускался.
    """
    if not initData:
        raise Exception("initData is empty")
    # Возвращаем tg_user_id, first_name, username
    return (7356182654, "Admin", "admin")  # <- временно


@app.get("/health")
def health():
    return {"ok": True, "public_url": PUBLIC_WEBAPP_URL}


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
    orders = list_orders_for_user(tg_user_id, 50)

    return [{
        "id": o["id"],
        "status": o["status"],
        "currency": o["currency"],
        "amount": o["amount"],
        "gift_delivered": bool(o["gift_delivered"]),
        "delivered_code": o["delivered_code"],
        "product_id": o["product_id"],
        "created_at": o["created_at"],
    } for o in orders]


@app.post("/api/orders")
async def make_order(req: Request, initData: str):
    """
    WebApp НЕ отправляет invoice.
    Она только создаёт заказ.
    Дальше ты выдаёшь кнопки оплаты в боте.
    """
    try:
        tg_user_id, first_name, username = validate_init(initData)
    except Exception:
        raise HTTPException(401, "Unauthorized")

    get_or_create_user(tg_user_id, first_name, username)

    body = await req.json()
    pid = int(body.get("product_id", 0))

    p = get_product(pid)
    if not p:
        raise HTTPException(404, "Product not found")

    order_id = create_order(
        tg_user_id=tg_user_id,
        product_id=pid,
        currency=p["currency_provider"],
        amount=p["price_provider"],
    )

    return {"ok": True, "order_id": order_id}


@app.on_event("startup")
async def _startup():
    init_db()
