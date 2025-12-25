import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = os.getenv("DB_PATH", "/home/GiftUpR0bot/GiftShopPro/shop.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    return con


def init_db():
    with _conn() as con:
        cur = con.cursor()

        # PRODUCTS
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

        # USERS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT
        )
        """)

        # ORDERS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            currency TEXT NOT NULL,
            amount INTEGER NOT NULL,
            gift_delivered INTEGER DEFAULT 0,
            delivered_code TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)

        con.commit()

    # seed products если пусто
    if len(list_products(True)) == 0:
        seed_products()


# -------------------------
# PRODUCTS
# -------------------------

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
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY id DESC"

    with _conn() as con:
        cur = con.cursor()
        cur.execute(q)
        rows = cur.fetchall()

    return [{
        "id": r[0],
        "title": r[1],
        "description": r[2],
        "price_provider": r[3],
        "currency_provider": r[4],
        "price_stars": r[5],
        "image_url": r[6],
        "is_active": r[7]
    } for r in rows]


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
        SELECT id, title, description, price_provider, currency_provider, price_stars, image_url, is_active
        FROM products WHERE id=?
        """, (product_id,))
        r = cur.fetchone()

    if not r:
        return None

    return {
        "id": r[0],
        "title": r[1],
        "description": r[2],
        "price_provider": r[3],
        "currency_provider": r[4],
        "price_stars": r[5],
        "image_url": r[6],
        "is_active": r[7]
    }


# -------------------------
# USERS
# -------------------------

def get_or_create_user(tg_user_id: int, first_name: str = "", username: str = "") -> int:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT tg_user_id FROM users WHERE tg_user_id=?", (tg_user_id,))
        row = cur.fetchone()

        if row:
            # обновим имя/username если изменилось
            cur.execute("""
                UPDATE users SET first_name=?, username=?
                WHERE tg_user_id=?
            """, (first_name or "", username or "", tg_user_id))
            con.commit()
            return tg_user_id

        cur.execute("""
            INSERT INTO users(tg_user_id, first_name, username)
            VALUES (?, ?, ?)
        """, (tg_user_id, first_name or "", username or ""))
        con.commit()
        return tg_user_id


# -------------------------
# ORDERS
# -------------------------

def create_order(tg_user_id: int, product_id: int, currency: str, amount: int) -> int:
    from datetime import datetime
    created_at = datetime.utcnow().isoformat()

    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO orders(tg_user_id, product_id, status, currency, amount, created_at)
            VALUES (?, ?, 'created', ?, ?, ?)
        """, (tg_user_id, product_id, currency, amount, created_at))
        con.commit()
        return cur.lastrowid


def list_orders_for_user(tg_user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, status, currency, amount, gift_delivered, delivered_code, product_id, created_at
            FROM orders
            WHERE tg_user_id=?
            ORDER BY id DESC
            LIMIT ?
        """, (tg_user_id, limit))
        rows = cur.fetchall()

    return [{
        "id": r[0],
        "status": r[1],
        "currency": r[2],
        "amount": r[3],
        "gift_delivered": r[4],
        "delivered_code": r[5],
        "product_id": r[6],
        "created_at": r[7],
    } for r in rows]
