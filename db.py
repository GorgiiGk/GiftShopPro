import os
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "/home/yourusername/GiftShopPro/shop.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            created_at TEXT
        )
        """)

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

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount INTEGER NOT NULL,
            gift_delivered INTEGER DEFAULT 0,
            delivered_code TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)

        con.commit()

    # добавим демо-продукты если пусто
    if len(list_products(active_only=False)) == 0:
        seed_products()


def seed_products():
    demo = [
        {
            "title": "Steam Gift Card 10$",
            "description": "Digital code delivery after payment",
            "price_provider": 10,
            "currency_provider": os.getenv("PROVIDER_CURRENCY", "RUB"),
            "
