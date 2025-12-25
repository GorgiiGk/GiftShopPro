import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.getenv("DB_PATH", "/home/GiftUpR0bot/GiftShopPro/shop.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price_provider INTEGER NOT NULL,
            currency_provider TEXT NOT NULL,
            price_stars INTEGER DEFAULT 0,
            image_url TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1
        )
        """)

        con.commit()

    # Если пусто — добавим пару тестовых товаров
    if len(list_products(True)) == 0:
        seed_products()


def seed_products():
    add_product(
        title="Steam Gift Card 10$",
        description="Digital code delivery after payment",
        price_provider=10,
        currency_provider=os.getenv("PROVIDER_CURRENCY", "RUB"),
        price_stars=100,
        image_url="https://i.imgur.com/D6G1bXQ.png",
        is_active=1
    )
    add_product(
        title="Netflix 1 month",
        description="Subscription code",
        price_provider=15,
        currency_provider=os.getenv("PROVIDER_CURRENCY", "RUB"),
        price_stars=150,
        image_url="https://i.imgur.com/D6G1bXQ.png",
        is_active=1
    )


def add_product(title: str, description: str, price_provider: int, currency_provider: str,
                price_stars: int = 0, image_url: str = "", is_active: int = 1):
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
        INSERT INTO products(title, description, price_provider, currency_provider, price_stars, image_url, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, description, price_provider, currency_provider, price_stars, image_url, is_active))
        con.commit()


def list_products(active_only=True) -> List[Dict[str, Any]]:
    q = "SELECT id, title, description, price_provider, currency_provider, price_stars, image_url, is_active FROM products"
    params = []
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY id DESC"

    with _conn() as con:
        cur = con.cursor()
        cur.execute(q, params)
        rows = cur.fetchall()

    res = []
    for r in rows:
        res.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "price_provider": r[3],
            "currency_provider": r[4],
            "price_stars": r[5],
            "image_url": r[6],
            "is_active": r[7]
        })
    return res
