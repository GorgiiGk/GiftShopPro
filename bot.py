import os, secrets, logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
)

from db import (
    init_db, get_or_create_user, list_products, get_product,
    create_product, add_codes, create_order,
    find_order, mark_paid, fulfill, list_orders_for_user, list_recent_orders
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
PROVIDER_TOKEN = os.getenv("TELEGRAM_PROVIDER_TOKEN","").strip()
PUBLIC_WEBAPP_URL = os.getenv("PUBLIC_WEBAPP_URL","").strip()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()]
PROVIDER_CURRENCY = os.getenv("PROVIDER_CURRENCY","RUB").upper()

if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN missing")
if not PUBLIC_WEBAPP_URL: raise RuntimeError("PUBLIC_WEBAPP_URL missing")

def is_admin(uid: int) -> bool: return uid in ADMIN_IDS

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Open shop", web_app={"url": PUBLIC_WEBAPP_URL})],
        [InlineKeyboardButton("Catalog", callback_data="catalog")],
        [InlineKeyboardButton("Orders", callback_data="orders")]
    ])

def kb_product(pid: int, has_provider: bool, has_stars: bool):
    rows = []
    if has_provider:
        rows.append([InlineKeyboardButton("Pay via provider", callback_data=f"buy:provider:{pid}")])
    if has_stars:
        rows.append([InlineKeyboardButton("Pay with Stars", callback_data=f"buy:stars:{pid}")])
    rows.append([InlineKeyboardButton("Back", callback_data="catalog")])
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the shop or catalog to purchase.", reply_markup=kb_main())

async def catalog_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ps = list_products(True)
    if not ps:
        await q.edit_message_text("No products available.", reply_markup=kb_main())
        return
    lines = []
    for p in ps[:20]:
        prov = f"{p['price_provider']/100:.2f} {p['currency_provider']}" if p["price_provider"] > 0 else None
        stars = f"{p['price_stars']} Stars" if p["price_stars"] > 0 else None
        price = " / ".join([x for x in [prov, stars] if x])
        lines.append(f"{p['id']}. {p['title']} — {price}")
    text = "Catalog:\n" + "\n".join(lines) + "\n\nSend /buy <id> or tap a product in WebApp."
    await q.edit_message_text(text, reply_markup=kb_main())

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /buy <product_id>
    args = update.message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await update.message.reply_text("Usage: /buy <product_id>", reply_markup=kb_main())
        return
    pid = int(args[1])
    p = get_product(pid)
    if not p:
        await update.message.reply_text("Product not found.", reply_markup=kb_main())
        return
    prov = p["price_provider"] > 0
    stars = p["price_stars"] > 0
    text = f"{p['title']}\n\n{p['description']}"
    await update.message.reply_text(text, reply_markup=kb_product(pid, prov, stars))

async def orders_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    os_ = list_orders_for_user(q.from_user.id, 10)
    if not os_:
        await q.edit_message_text("No orders yet.", reply_markup=kb_main())
        return
    out = []
    for o in os_:
        amt = f"{o['amount']} Stars" if o["currency"] == "XTR" else f"{o['amount']/100:.2f} {o['currency']}"
        line = f"Order #{o['id']}: {o['status']} ({amt})"
        if o["gift_delivered"] and o["delivered_code"]:
            line += f"\nCode:\n{o['delivered_code']}"
        out.append(line)
    await q.edit_message_text("\n\n".join(out), reply_markup=kb_main())

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pq = update.pre_checkout_query
    if not find_order(pq.invoice_payload):
        await pq.answer(ok=False, error_message="Order not found.")
        return
    await pq.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    if not find_order(payload):
        await update.message.reply_text("Payment received, but order not found.")
        return
    mark_paid(payload)
    try:
        code = fulfill(payload)
        await update.message.reply_text(f"Payment confirmed.\n\nYour code:\n{code}", reply_markup=kb_main())
    except Exception:
        await update.message.reply_text("Payment confirmed.\nDelivery unavailable (no codes in stock).", reply_markup=kb_main())

async def buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, method, pid = q.data.split(":")
    pid = int(pid)

    p = get_product(pid)
    if not p:
        await q.edit_message_text("Product not found.", reply_markup=kb_main())
        return

    tg_user_id = q.from_user.id
    uid = get_or_create_user(tg_user_id, q.from_user.first_name, q.from_user.username)
    payload = f"order_{secrets.token_urlsafe(18)}"

    if method == "stars":
        if p["price_stars"] <= 0:
            await q.edit_message_text("Stars payment is not available for this product.", reply_markup=kb_main())
            return
        amount = int(p["price_stars"])
        create_order(tg_user_id, uid, pid, "stars", "XTR", amount, payload)
        await context.bot.send_invoice(
            chat_id=tg_user_id,
            title=p["title"][:32],
            description=(p["description"] or "Digital product")[:255],
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Stars", amount=amount)],
        )
        await q.edit_message_text("Invoice sent.", reply_markup=kb_main())
        return

    # provider method
    if p["price_provider"] <= 0:
        await q.edit_message_text("Provider payment is not available for this product.", reply_markup=kb_main())
        return
    if not PROVIDER_TOKEN:
        await q.edit_message_text("Provider token is not configured.", reply_markup=kb_main())
        return
    amount = int(p["price_provider"])
    create_order(tg_user_id, uid, pid, "provider", p["currency_provider"], amount, payload)
    await context.bot.send_invoice(
        chat_id=tg_user_id,
        title=p["title"][:32],
        description=(p["description"] or "Digital product")[:255],
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=p["currency_provider"],
        prices=[LabeledPrice(label=p["title"][:32], amount=amount)],
    )
    await q.edit_message_text("Invoice sent.", reply_markup=kb_main())

# -------- Admin --------
async def add_product_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    raw = update.message.text.replace("/add_product","",1).strip()
    # /add_product <provider_cents> <stars> | <title> | <description> | <image_or_->
    try:
        parts = [p.strip() for p in raw.split("|")]
        head = parts[0].split()
        provider_price = int(head[0])
        stars_price = int(head[1])
        title = parts[1]
        desc = parts[2] if len(parts) > 2 else ""
        img = parts[3] if len(parts) > 3 else None
        if img in ("-", "", None): img = None
        pid = create_product(title, desc, provider_price, PROVIDER_CURRENCY, stars_price, img)
        await update.message.reply_text(f"Product created: id={pid}")
    except Exception:
        await update.message.reply_text("Format:\n/add_product <provider_cents> <stars> | <title> | <description> | <image_or_->_")

async def add_codes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    args = update.message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await update.message.reply_text("Format: /add_codes <product_id>")
        return
    context.user_data["await_codes_pid"] = int(args[1])
    await update.message.reply_text("Send codes in one message, one per line.")

async def receive_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    pid = context.user_data.get("await_codes_pid")
    if not pid: return
    codes = [x.strip() for x in (update.message.text or "").splitlines() if x.strip()]
    n = add_codes(pid, codes)
    context.user_data.pop("await_codes_pid", None)
    await update.message.reply_text(f"Codes added: {n}")

async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    ps = list_products(False)[:30]
    if not ps:
        await update.message.reply_text("No products.")
        return
    lines=[]
    for p in ps:
        lines.append(f"{p['id']}: {p['title']} | provider={p['price_provider']} {p['currency_provider']} | stars={p['price_stars']} | active={p['is_active']}")
    await update.message.reply_text("\n".join(lines))

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    os_ = list_recent_orders(20)
    if not os_:
        await update.message.reply_text("No orders.")
        return
    lines=[]
    for o in os_:
        amt = f"{o['amount']} Stars" if o["currency"] == "XTR" else f"{o['amount']/100:.2f} {o['currency']}"
        lines.append(f"{o['id']}: user={o['tg_user_id']} product={o['product_id']} {o['status']} ({amt})")
    await update.message.reply_text("\n".join(lines))

def build():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy_cmd))

    app.add_handler(CallbackQueryHandler(catalog_cb, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(orders_cb, pattern="^orders$"))
    app.add_handler(CallbackQueryHandler(buy_cb, pattern="^buy:(provider|stars):\\d+$"))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    app.add_handler(CommandHandler("add_product", add_product_cmd))
    app.add_handler(CommandHandler("add_codes", add_codes_cmd))
    app.add_handler(CommandHandler("products", admin_products))
    app.add_handler(CommandHandler("admin_orders", admin_orders))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_codes))
    return app

def main():
    init_db()
    build().run_polling(close_loop=False)

if __name__ == "__main__":
    main()
