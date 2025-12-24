import os, sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "shop.db")

def now_iso(): return datetime.now(timezone.utc).isoformat()

def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_user_id INTEGER UNIQUE NOT NULL,
      first_name TEXT, username TEXT,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      price_provider INTEGER NOT NULL DEFAULT 0,
      currency_provider TEXT NOT NULL DEFAULT 'RUB',
      price_stars INTEGER NOT NULL DEFAULT 0,
      image_url TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS gift_codes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id INTEGER NOT NULL,
      code TEXT NOT NULL,
      is_used INTEGER NOT NULL DEFAULT 0,
      used_by_order_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_user_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      pay_method TEXT NOT NULL,            -- provider|stars
      currency TEXT NOT NULL,              -- RUB / XTR
      amount INTEGER NOT NULL,
      status TEXT NOT NULL,                -- invoice_sent|paid|fulfilled|failed
      invoice_payload TEXT UNIQUE NOT NULL,
      gift_delivered INTEGER NOT NULL DEFAULT 0,
      delivered_code TEXT,
      created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(tg_user_id);
    CREATE INDEX IF NOT EXISTS idx_codes ON gift_codes(product_id, is_used);
    """)
    c.commit(); c.close()

def get_or_create_user(tg_user_id, first_name=None, username=None):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT id FROM users WHERE tg_user_id=?", (tg_user_id,))
    r = cur.fetchone()
    if r:
        cur.execute("UPDATE users SET first_name=?, username=? WHERE tg_user_id=?",
                    (first_name, username, tg_user_id))
        c.commit(); c.close()
        return int(r["id"])
    cur.execute("INSERT INTO users(tg_user_id, first_name, username, created_at) VALUES(?,?,?,?)",
                (tg_user_id, first_name, username, now_iso()))
    c.commit(); uid = cur.lastrowid
    c.close()
    return int(uid)

def list_products(active_only=True):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT * FROM products WHERE is_active=1 ORDER BY id DESC" if active_only
                else "SELECT * FROM products ORDER BY id DESC")
    rows = [dict(x) for x in cur.fetchall()]
    c.close()
    return rows

def get_product(pid):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT * FROM products WHERE id=? AND is_active=1", (pid,))
    r = cur.fetchone()
    c.close()
    return dict(r) if r else None

def create_product(title, description, price_provider, currency_provider, price_stars, image_url):
    c = conn(); cur = c.cursor()
    cur.execute("""INSERT INTO products(title,description,price_provider,currency_provider,price_stars,image_url,is_active,created_at)
                   VALUES(?,?,?,?,?,?,1,?)""",
                (title, description, int(price_provider), currency_provider, int(price_stars), image_url, now_iso()))
    c.commit(); pid = cur.lastrowid
    c.close()
    return int(pid)

def add_codes(product_id, codes):
    c = conn(); cur = c.cursor()
    n = 0
    for code in codes:
        code = code.strip()
        if not code: continue
        cur.execute("INSERT INTO gift_codes(product_id, code, is_used) VALUES(?,?,0)", (int(product_id), code))
        n += 1
    c.commit(); c.close()
    return n

def create_order(tg_user_id, user_id, product_id, pay_method, currency, amount, payload):
    c = conn(); cur = c.cursor()
    cur.execute("""INSERT INTO orders(tg_user_id,user_id,product_id,pay_method,currency,amount,status,invoice_payload,created_at)
                   VALUES(?,?,?,?,? ,?,'invoice_sent',?,?)""",
                (tg_user_id, user_id, int(product_id), pay_method, currency, int(amount), payload, now_iso()))
    c.commit(); oid = cur.lastrowid
    c.close()
    return int(oid)

def find_order(payload):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT * FROM orders WHERE invoice_payload=?", (payload,))
    r = cur.fetchone()
    c.close()
    return dict(r) if r else None

def list_orders_for_user(tg_user_id, limit=50):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT * FROM orders WHERE tg_user_id=? ORDER BY id DESC LIMIT ?", (tg_user_id, int(limit)))
    rows = [dict(x) for x in cur.fetchall()]
    c.close()
    return rows

def list_recent_orders(limit=20):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (int(limit),))
    rows = [dict(x) for x in cur.fetchall()]
    c.close()
    return rows

def mark_paid(payload):
    c = conn()
    c.execute("UPDATE orders SET status='paid' WHERE invoice_payload=?", (payload,))
    c.commit(); c.close()

def fulfill(payload):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT id, product_id FROM orders WHERE invoice_payload=?", (payload,))
    o = cur.fetchone()
    if not o: c.close(); raise RuntimeError("order not found")

    order_id = int(o["id"])
    product_id = int(o["product_id"])

    c.execute("BEGIN IMMEDIATE;")
    cur.execute("""SELECT id, code FROM gift_codes
                   WHERE product_id=? AND is_used=0
                   ORDER BY id ASC LIMIT 1""", (product_id,))
    code_row = cur.fetchone()
    if not code_row:
        c.execute("ROLLBACK;")
        c.close()
        raise RuntimeError("no codes")

    code_id = int(code_row["id"])
    code = str(code_row["code"])

    cur.execute("UPDATE gift_codes SET is_used=1, used_by_order_id=? WHERE id=?", (order_id, code_id))
    cur.execute("""UPDATE orders
                   SET status='fulfilled', gift_delivered=1, delivered_code=?
                   WHERE id=?""", (code, order_id))
    c.commit(); c.close()
    return code
