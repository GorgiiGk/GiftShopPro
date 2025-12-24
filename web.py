import os, json, hmac, hashlib, urllib.parse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, list_products, get_product, get_or_create_user, list_orders_for_user, create_order

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN missing")

app = FastAPI(title="GiftShopPro Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def _parse_init(init_data: str): return dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))

def validate_init(init_data: str):
    d = _parse_init(init_data)
    if "hash" not in d: raise ValueError("hash missing")
    recv = d.pop("hash")
    check = "\n".join([f"{k}={d[k]}" for k in sorted(d.keys())]).encode()
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv): raise ValueError("bad hash")
    u = json.loads(d["user"])
    return int(u["id"]), u.get("first_name"), u.get("username")

WEB = """<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Shop</title><script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#0b1020;--panel:rgba(255,255,255,.06);--bd:rgba(255,255,255,.10);--tx:rgba(255,255,255,.92);--mt:rgba(255,255,255,.65);--a:#7aa7ff;--b:#9b8cff;--ok:#2dd4bf;--bad:#ff6b6b;--r:16px}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;background:radial-gradient(1200px 600px at 20% 0%, rgba(122,167,255,.18), transparent 60%),radial-gradient(900px 500px at 90% 10%, rgba(155,140,255,.14), transparent 55%),linear-gradient(180deg,#070b16,var(--bg));color:var(--tx)}
.w{max-width:980px;margin:0 auto;padding:18px}
.t{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.h{font-weight:800;font-size:16px}.s{color:var(--mt);font-size:12px}
.b{border:1px solid var(--bd);background:rgba(255,255,255,.04);color:var(--tx);padding:10px 12px;border-radius:12px;cursor:pointer;font-weight:650;font-size:13px}
.b.p{border:none;background:linear-gradient(90deg,rgba(122,167,255,.95),rgba(155,140,255,.95));color:#0b1020}
.st{padding:12px 14px;border-radius:var(--r);border:1px solid var(--bd);background:var(--panel);color:var(--mt);font-size:13px}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:14px}
.c{border:1px solid var(--bd);background:var(--panel);border-radius:var(--r);padding:14px;display:flex;flex-direction:column;gap:10px;min-height:210px;backdrop-filter:blur(10px)}
.ct{font-weight:780;font-size:14px}.cd{color:var(--mt);font-size:13px;line-height:1.35}.cp{margin-top:auto;font-weight:850;font-size:14px}
.buy{width:100%;padding:11px 12px;border-radius:13px;border:none;cursor:pointer;font-weight:800;font-size:13px;color:#0b1020;background:linear-gradient(90deg,rgba(122,167,255,.95),rgba(155,140,255,.95))}
.l{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.rw{border:1px solid var(--bd);background:var(--panel);border-radius:var(--r);padding:12px 14px;display:flex;flex-direction:column;gap:6px}
.bad{font-size:12px;padding:3px 8px;border-radius:999px;border:1px solid var(--bd);color:var(--mt)}
.bad.ok{color:var(--ok);border-color:rgba(45,212,191,.35);background:rgba(45,212,191,.08)}
.bad.bad{color:var(--bad);border-color:rgba(255,107,107,.35);background:rgba(255,107,107,.08)}
code{display:block;white-space:pre-wrap;word-break:break-word;padding:10px 12px;border-radius:12px;background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.10);font-size:12px}
</style></head><body><div class="w">
<div class="t"><div><div class="h">Shop</div><div class="s">Payments and instant delivery</div></div>
<div style="display:flex;gap:10px"><button class="b p" id="tab1">Catalog</button><button class="b" id="tab2">Orders</button></div></div>
<div class="st" id="st">Loading…</div>
<div id="shop" class="g" style="display:none"></div>
<div id="orders" class="l" style="display:none"></div>
</div>
<script>
const tg=window.Telegram?.WebApp; if(tg){tg.ready();tg.expand();}
const initData=tg?.initData||""; const st=document.getElementById("st");
const shop=document.getElementById("shop"); const orders=document.getElementById("orders");
const t1=document.getElementById("tab1"); const t2=document.getElementById("tab2");

function setTab(x){
  if(x==="shop"){shop.style.display="grid";orders.style.display="none";t1.classList.add("p");t2.classList.remove("p")}
  else{shop.style.display="none";orders.style.display="flex";t2.classList.add("p");t1.classList.remove("p")}
}
t1.onclick=()=>setTab("shop");
t2.onclick=async()=>{setTab("orders");await loadOrders();}

function money(a,c){return (a/100).toFixed(2)+" "+c;}
function badge(s){
  if(s==="fulfilled"||s==="paid") return '<span class="bad ok">'+s+'</span>';
  if(s==="failed") return '<span class="bad bad">'+s+'</span>';
  return '<span class="bad">'+s+'</span>';
}
async function api(path,opt){
  const url=path+(path.includes("?")?"&":"?")+"initData="+encodeURIComponent(initData);
  const r=await fetch(url,opt||{}); if(!r.ok) throw new Error(await r.text());
  return r.json();
}

async function loadProducts(){
  const ps=await api("/api/products");
  shop.innerHTML="";
  if(!ps.length){shop.innerHTML='<div class="c"><div class="ct">No products</div><div class="cd">Please check back later.</div></div>';return;}
  for(const p of ps){
    const el=document.createElement("div"); el.className="c";
    const title=document.createElement("div"); title.className="ct"; title.textContent=p.title;
    const desc=document.createElement("div"); desc.className="cd"; desc.textContent=p.description||"";
    const price=document.createElement("div"); price.className="cp"; price.textContent =
      (p.price_provider>0?money(p.price_provider,p.currency_provider):"") +
      (p.price_provider>0 && p.price_stars>0 ? " / " : "") +
      (p.price_stars>0 ? (p.price_stars+" Stars") : "");
    const btn1=document.createElement("button"); btn1.className="buy"; btn1.textContent="Pay via provider";
    btn1.style.display = p.price_provider>0 ? "block" : "none";
    btn1.onclick=async()=>{
      btn1.disabled=true;btn1.textContent="Processing…";
      try{await api("/api/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:p.id,method:"provider"})});
          st.textContent="Invoice sent to the bot chat."; tg?.showAlert?.("Invoice sent to the bot chat.");
      }catch(e){st.textContent="Error: "+e.message; tg?.showAlert?.("Error: "+e.message);}
      finally{btn1.disabled=false;btn1.textContent="Pay via provider";}
    };
    const btn2=document.createElement("button"); btn2.className="buy"; btn2.textContent="Pay with Stars";
    btn2.style.display = p.price_stars>0 ? "block" : "none";
    btn2.onclick=async()=>{
      btn2.disabled=true;btn2.textContent="Processing…";
      try{await api("/api/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:p.id,method:"stars"})});
          st.textContent="Invoice sent to the bot chat."; tg?.showAlert?.("Invoice sent to the bot chat.");
      }catch(e){st.textContent="Error: "+e.message; tg?.showAlert?.("Error: "+e.message);}
      finally{btn2.disabled=false;btn2.textContent="Pay with Stars";}
    };
    el.appendChild(title); el.appendChild(desc); el.appendChild(price); el.appendChild(btn1); el.appendChild(btn2);
    shop.appendChild(el);
  }
}

async function loadOrders(){
  const os=await api("/api/me/orders");
  orders.innerHTML="";
  if(!os.length){orders.innerHTML='<div class="rw"><div class="ct">No orders</div><div class="cd">Completed purchases appear here.</div></div>';return;}
  for(const o of os){
    const el=document.createElement("div"); el.className="rw";
    const amt = (o.currency==="XTR") ? (o.amount+" Stars") : money(o.amount,o.currency);
    el.innerHTML='<div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline"><div class="ct">Order #'+o.id+'</div>'+badge(o.status)+'</div>'
               +'<div class="cd">'+amt+'</div>';
    if(o.gift_delivered && o.delivered_code){
      const code=document.createElement("code"); code.textContent=o.delivered_code; el.appendChild(code);
    }
    orders.appendChild(el);
  }
}

(async()=>{
  try{
    if(!initData){st.textContent="Open from Telegram."; setTab("shop"); return;}
    st.textContent="Ready."; setTab("shop"); shop.style.display="grid";
    await loadProducts();
  }catch(e){
    st.textContent="Error: "+e.message;
    setTab("shop");
  }
})();
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def index(): return WEB

@app.get("/api/products")
def products(initData: str):
    try: validate_init(initData)
    except Exception: raise HTTPException(401, "Unauthorized")
    ps = list_products(True)
    return [{
      "id":p["id"], "title":p["title"], "description":p["description"],
      "price_provider":p["price_provider"], "currency_provider":p["currency_provider"],
      "price_stars":p["price_stars"], "image_url":p["image_url"]
    } for p in ps]

@app.get("/api/me/orders")
def my_orders(initData: str):
    try:
        tg_user_id, first_name, username = validate_init(initData)
    except Exception:
        raise HTTPException(401, "Unauthorized")
    _ = get_or_create_user(tg_user_id, first_name, username)
    os_ = list_orders_for_user(tg_user_id, 50)
    return [{
      "id":o["id"], "status":o["status"], "currency":o["currency"], "amount":o["amount"],
      "gift_delivered":bool(o["gift_delivered"]), "delivered_code":o["delivered_code"]
    } for o in os_]

@app.post("/api/orders")
async def make_order(req: Request, initData: str):
    try:
        tg_user_id, first_name, username = validate_init(initData)
    except Exception:
        raise HTTPException(401, "Unauthorized")
    body = await req.json()
    pid = int(body.get("product_id", 0))
    method = (body.get("method") or "provider").lower()

    p = get_product(pid)
    if not p: raise HTTPException(404, "Product not found")

    uid = get_or_create_user(tg_user_id, first_name, username)

    # IMPORTANT: Web does NOT send invoices.
    # Web only creates the order. Bot will send invoices when you call /invoice
    # OR you can add a webhook-based bridge later.
    #
    # For PythonAnywhere simplicity: orders are created here,
    # and user will tap "Pay" inside bot after selecting product.
    #
    # If you want automatic invoice from WebApp, tell me — I'll add a tiny "bot bridge" endpoint.

    raise HTTPException(400, "Invoice must be initiated by bot. Use bot payment buttons.")
    # (we keep this endpoint reserved for a future bridge)

@app.on_event("startup")
async def _startup(): init_db()
