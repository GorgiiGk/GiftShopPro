import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from db import init_db, list_products

# Загружаем .env (если есть)
load_dotenv()

app = FastAPI(title="GiftShopPro Web")


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/")
def root():
    return {"ok": True, "service": "GiftShopPro Web"}


@app.get("/api/products")
def products():
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
