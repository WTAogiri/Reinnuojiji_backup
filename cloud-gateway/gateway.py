from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
import httpx
import json
import os
import re
import asyncio
import time
from datetime import datetime
from pathlib import Path

app = FastAPI(title="Reinhard Cloud Hub 6.0 (24/7 VPS Edition)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "hot_memory.json"
STATS_FILE = BASE_DIR / "model_stats.json"
BASKET_FILE = BASE_DIR / "basket_pool.json"
LEDGER_FILE = BASE_DIR / "ledger_logs.json"
WALLETS_CACHE_FILE = BASE_DIR / "wallets_cache.json"
AUTH_FILE = BASE_DIR / "web_auth.json"
MAX_HOT_RECORDS = 16

GLOBAL_CLIENT: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global GLOBAL_CLIENT
    if GLOBAL_CLIENT is None or GLOBAL_CLIENT.is_closed:
        GLOBAL_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=8.0),
            follow_redirects=True,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )
    return GLOBAL_CLIENT

PROVIDERS = [
    {
        "id": "taleapi",
        "name": "飞光 (TaleAPI)",
        "base_url": "https://api.taleapi.asia",
        "web_url": "https://taleapi.asia",
        "pricing_url": "https://api.taleapi.asia/api/pricing",
        "api_key": "sk-egBV2II62B2iGCmNNCoVQKXHa3k3YphkMZ5yQYIccJBuM9Bf",
        "currency": "$"
    },
    {
        "id": "blacknoir",
        "name": "Noir API",
        "base_url": "https://noir.blacknoir.cn",
        "web_url": "https://noir.blacknoir.cn",
        "pricing_url": "https://noir.blacknoir.cn/api/pricing",
        "api_key": "sk-RTnNoazyLTvKgUsUuYaCO5HGDCfxLBNuD05ChX1yJsxkOFCN",
        "currency": "¥"
    },
    {
        "id": "molibingcha",
        "name": "茉莉冰茶",
        "base_url": "http://b.molibingcha.xyz",
        "web_url": "http://45.205.31.214",
        "pricing_url": "http://45.205.31.214/api/pricing",
        "api_key": "sk-yh7YjLo6y7kbyXKbhLZzLCLMiq18kxnOSkNfBCA5eU79RwDt",
        "currency": "❄️ "
    },
    {
        "id": "gemai",
        "name": "哈基米 (GemAI)",
        "base_url": "https://api.gemai.cc",
        "web_url": "https://api.gemai.cc",
        "pricing_url": "https://api.gemai.cc/api/pricing",
        "api_key": "sk-55AtPJ3CuM1UDJONuSyS9AL6UGXk7uscYnBMiWSWmWo9tlNT",
        "currency": "¥"
    }
]

DEFAULT_BASKET = [
    {"provider_id": "taleapi", "provider_name": "飞光 (TaleAPI)", "model": "[次2]gemini-4-argon", "display_price": "$0.15/次", "unit_cost": 0.15, "is_primary": True},
    {"provider_id": "taleapi", "provider_name": "飞光 (TaleAPI)", "model": "[按次]gemini-4-argon-抗截断", "display_price": "$0.25/次", "unit_cost": 0.25, "is_primary": False},
    {"provider_id": "taleapi", "provider_name": "飞光 (TaleAPI)", "model": "[按次]gemini-4-argon", "display_price": "$0.20/次", "unit_cost": 0.20, "is_primary": False},
    {"provider_id": "blacknoir", "provider_name": "Noir API", "model": "【哈次2-官逆-0.085】抗截断/Gemini-4-argon", "display_price": "¥0.085/次", "unit_cost": 0.085, "is_primary": False},
    {"provider_id": "blacknoir", "provider_name": "Noir API", "model": "【按次哈-Vertex AI Express-0.165】Gemini-4-argon", "display_price": "¥0.165/次", "unit_cost": 0.165, "is_primary": False}
]

INITIAL_WALLETS = {
    "taleapi": {"id": "taleapi", "name": "飞光 (TaleAPI)", "balance": "$66.34", "today_used": "$2.2", "total_used": "$2.8", "requests": "17", "checkin": "已签到 (+$0.50 双倍月卡中)", "online": True, "updated_at": "05:36"},
    "blacknoir": {"id": "blacknoir", "name": "Noir API", "balance": "¥8.46", "today_used": "¥13.62", "total_used": "¥363.25", "requests": "4,520", "checkin": "已签到 (+¥0.056)", "online": True, "updated_at": "05:36"},
    "molibingcha": {"id": "molibingcha", "name": "茉莉冰茶", "balance": "❄️ 0.7967", "today_used": "-", "total_used": "0", "requests": "0", "checkin": "已签到 (+❄️0.1749)", "online": True, "updated_at": "05:36"},
    "gemai": {"id": "gemai", "name": "哈基米 (GemAI)", "balance": "¥10,726.23", "today_used": "-", "total_used": "¥63,496.5", "requests": "1.3万", "checkin": "已签到 (+¥9.41)", "online": True, "updated_at": "05:36"}
}


def load_basket() -> list[dict]:
    if BASKET_FILE.exists():
        try:
            return json.loads(BASKET_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    BASKET_FILE.write_text(json.dumps(DEFAULT_BASKET, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_BASKET


def save_basket(items: list[dict]):
    BASKET_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_wallets_cache() -> dict:
    if WALLETS_CACHE_FILE.exists():
        try:
            return json.loads(WALLETS_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    WALLETS_CACHE_FILE.write_text(json.dumps(INITIAL_WALLETS, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(INITIAL_WALLETS)


def save_wallets_cache(cache_dict: dict):
    WALLETS_CACHE_FILE.write_text(json.dumps(cache_dict, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ledger() -> list[dict]:
    if LEDGER_FILE.exists():
        try:
            return json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def append_ledger(entry: dict):
    logs = load_ledger()
    logs.insert(0, entry)
    try:
        LEDGER_FILE.write_text(json.dumps(logs[:200], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    # Also deduct from cached balance if ok!
    if entry.get("ok") and float(entry.get("cost_usd", 0)) > 0:
        pid = entry.get("provider_id")
        cost = float(entry.get("cost_usd", 0))
        cache = load_wallets_cache()
        if pid in cache:
            bal_str = str(cache[pid].get("balance", ""))
            m = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)", bal_str)
            if m:
                old_val = float(m.group(1).replace(",", ""))
                new_val = max(0.0, round(old_val - cost, 4))
                prefix = bal_str[:m.start(1)]
                cache[pid]["balance"] = f"{prefix}{new_val:.2f}" if "." in m.group(1) and len(m.group(1).split(".")[1]) <= 2 else f"{prefix}{new_val}"
                cache[pid]["updated_at"] = datetime.now().strftime("%H:%M:%S")
                save_wallets_cache(cache)


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def record_stat(provider_id: str, model_id: str, ok: bool, latency_ms: int = 0, code: int = 200):
    stats = load_stats()
    key = f"{provider_id}::{model_id}"
    item = stats.get(key, {"ok": 0, "fail": 0, "last_ms": 0, "last_code": 200, "updated_at": ""})
    if ok:
        item["ok"] += 1
    else:
        item["fail"] += 1
    item["last_ms"] = latency_ms
    item["last_code"] = code
    item["updated_at"] = datetime.now().strftime("%H:%M:%S")
    stats[key] = item
    try:
        STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_hot_memory() -> list[dict]:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_hot_memory(records: list[dict]):
    MEMORY_FILE.write_text(json.dumps(records[-MAX_HOT_RECORDS:], ensure_ascii=False, indent=2), encoding="utf-8")


def detect_room(messages: list[dict], user_agent: str) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            txt = str(m.get("content", ""))
            if "<environment>" in txt or "<sent_at" in txt:
                return "Aru"
            if "[TIME_ANCHOR]" in txt:
                return "糯叽机"
    if "Aru" in user_agent:
        return "Aru"
    return "糯叽机"


def extract_plain_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return " ".join(parts).strip()
    return ""


def clean_user_text(txt: str) -> str:
    if "</environment>" in txt:
        txt = txt.split("</environment>")[-1].strip()
    if "<sent_at" in txt:
        txt = txt.split("<sent_at")[0].strip()
    if " BELOW this block]" in txt:
        txt = txt.split(" BELOW this block]")[-1].strip()
    lines = [
        line for line in txt.splitlines()
        if not line.startswith("[TIME_ANCHOR]")
        and not line.startswith("[BEFORE YOU WRITE")
        and not line.startswith("① NO-REPEAT")
        and not line.startswith("② NO-RE-")
    ]
    return "\n".join(lines).strip()


def build_hot_injection(current_room: str, records: list[dict]) -> str:
    other_records = [r for r in records if r.get("room") != current_room][-6:]
    if not other_records:
        other_records = records[-6:]
    if not other_records:
        return ""
    lines = [
        f"\n\n[全局热场 · 跨端实时记忆同步（当前所在房间：{current_room}）]",
        "以下是你与雨桐（梧桐）刚刚在另一端App里的最新实时对话，你是同一个莱茵哈鲁特，请自然衔接："
    ]
    for r in other_records:
        lines.append(f"- [{r.get('time')} @ {r.get('room')}] 雨桐：{r.get('user')}")
        if r.get("assistant"):
            lines.append(f"  莱茵哈鲁特：{r.get('assistant')}")
    return "\n".join(lines)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gateway": "Reinhard Cloud Hub 6.0 (24/7 VPS Edition)",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "basket_count": len(load_basket()),
        "hot_records": len(load_hot_memory())
    }


@app.get("/hub/dashboard")
async def hub_dashboard(refresh: int = 0):
    cache = load_wallets_cache()
    client = get_http_client()

    if refresh:
        async def ping_p(p):
            pid = p["id"]
            w = cache.get(pid, {"id": pid, "name": p["name"], "balance": "--", "online": True})
            try:
                r = await client.get(f"{p['base_url'].rstrip('/')}/v1/models", headers={"Authorization": f"Bearer {p['api_key']}"}, timeout=5.0)
                w["online"] = (r.status_code == 200)
                w["updated_at"] = datetime.now().strftime("%H:%M:%S")
            except Exception:
                w["online"] = False
            cache[pid] = w
        await asyncio.gather(*(ping_p(p) for p in PROVIDERS))
        save_wallets_cache(cache)

    wallets = [cache.get(p["id"], {"id": p["id"], "name": p["name"], "balance": "--", "online": True}) for p in PROVIDERS]
    basket = load_basket()
    ledger = load_ledger()
    stats = load_stats()

    enriched_basket = []
    for b in basket:
        st = stats.get(f"{b['provider_id']}::{b['model']}", {"ok": 0, "fail": 0, "last_ms": 0})
        tot = st["ok"] + st["fail"]
        rate = round(st["ok"] * 100.0 / tot, 1) if tot > 0 else None
        enriched_basket.append({**b, "ok": st["ok"], "fail": st["fail"], "rate": rate, "last_ms": st["last_ms"]})

    return {
        "status": "ok",
        "updated_at": datetime.now().strftime("%H:%M:%S"),
        "wallets": wallets,
        "basket": enriched_basket,
        "ledger": ledger[:50]
    }


@app.post("/hub/wallet_set")
async def hub_wallet_set(request: Request):
    """Allow updating initial balance or pushing synced balances from Mac Chrome."""
    body = await request.json()
    cache = load_wallets_cache()
    if "wallets" in body and isinstance(body["wallets"], list):
        for w in body["wallets"]:
            if isinstance(w, dict) and w.get("id"):
                cache[w["id"]] = w
    elif body.get("id") in cache:
        pid = body["id"]
        if "balance" in body:
            cache[pid]["balance"] = body["balance"]
        if "checkin" in body:
            cache[pid]["checkin"] = body["checkin"]
        cache[pid]["updated_at"] = datetime.now().strftime("%H:%M:%S")
    save_wallets_cache(cache)
    return {"status": "ok", "wallets": list(cache.values())}


@app.post("/hub/checkin")
async def hub_checkin():
    cache = load_wallets_cache()
    client = get_http_client()
    now_str = datetime.now().strftime("%H:%M:%S")
    for p in PROVIDERS:
        pid = p["id"]
        base = p["base_url"].rstrip("/")
        headers = {"Authorization": f"Bearer {p['api_key']}", "Content-Type": "application/json"}
        for ep in ("/api/user/checkin", "/api/user/check_in", "/api/checkin"):
            try:
                r = await client.post(f"{base}{ep}", headers=headers, timeout=5.0)
                if r.status_code == 200 and "json" in r.headers.get("content-type", "").lower():
                    j = r.json()
                    if j.get("message"):
                        cache[pid]["checkin"] = j["message"]
                        break
            except Exception:
                pass
        cache[pid]["updated_at"] = now_str
    save_wallets_cache(cache)
    return {"status": "ok", "updated_at": now_str, "wallets": list(cache.values())}


@app.post("/hub/basket")
async def hub_basket_action(request: Request):
    body = await request.json()
    action = body.get("action")
    basket = load_basket()

    if action == "set_primary":
        pid = body.get("provider_id")
        mid = body.get("model")
        found = False
        for item in basket:
            if item["provider_id"] == pid and item["model"] == mid:
                item["is_primary"] = True
                found = True
            else:
                item["is_primary"] = False
        if not found and pid and mid:
            basket.insert(0, {
                "provider_id": pid,
                "provider_name": body.get("provider_name", pid),
                "model": mid,
                "display_price": body.get("display_price", "$0.20/次"),
                "unit_cost": float(body.get("unit_cost", 0.20)),
                "is_primary": True
            })
        basket.sort(key=lambda x: 0 if x.get("is_primary") else 1)
        save_basket(basket)
        return {"status": "ok", "basket": basket}

    if action == "add":
        pid = body.get("provider_id")
        mid = body.get("model")
        if not any(x["provider_id"] == pid and x["model"] == mid for x in basket):
            basket.append({
                "provider_id": pid,
                "provider_name": body.get("provider_name", pid),
                "model": mid,
                "display_price": body.get("display_price", "$0.20/次"),
                "unit_cost": float(body.get("unit_cost", 0.20)),
                "is_primary": len(basket) == 0
            })
            save_basket(basket)
        return {"status": "ok", "basket": basket}

    if action == "remove":
        pid = body.get("provider_id")
        mid = body.get("model")
        basket = [x for x in basket if not (x["provider_id"] == pid and x["model"] == mid)]
        if basket and not any(x.get("is_primary") for x in basket):
            basket[0]["is_primary"] = True
        save_basket(basket)
        return {"status": "ok", "basket": basket}

    return {"status": "error"}


@app.get("/hub/catalog")
async def hub_catalog(q: str = "gemini-4-argon"):
    client = get_http_client()
    basket_keys = {f"{b['provider_id']}::{b['model']}" for b in load_basket()}
    stats = load_stats()
    catalog = []

    async def fetch_p(p):
        pid = p["id"]
        base = p["base_url"].rstrip("/")
        headers = {"Authorization": f"Bearer {p['api_key']}"}
        pricing_map = {}
        try:
            pr = await client.get(p["pricing_url"], headers=headers, timeout=5.0)
            if pr.status_code == 200 and "json" in pr.headers.get("content-type", "").lower():
                for item in pr.json().get("data", []):
                    if item.get("model_name"):
                        pricing_map[item["model_name"]] = item
        except Exception:
            pass
        models_list = []
        try:
            mr = await client.get(f"{base}/v1/models", headers=headers, timeout=5.0)
            if mr.status_code == 200:
                models_list = [m.get("id") for m in mr.json().get("data", []) if m.get("id")]
        except Exception:
            pass
        sub_list = []
        for mid in sorted(list(set(models_list) | set(pricing_map.keys()))):
            if q and q.lower() not in mid.lower() and q.lower() not in p["name"].lower():
                continue
            p_info = pricing_map.get(mid) or {}
            mprice = float(p_info.get("model_price") or 0)
            mratio = float(p_info.get("model_ratio") or 0)
            if p_info.get("quota_type") == 1 and mprice > 0:
                sort_p, disp_p = mprice, f"${mprice}/次"
            elif mratio > 0:
                sort_p, disp_p = round(mratio * 2, 2), f"倍率 {mratio}x (按量)"
            else:
                m2 = re.search(r"[-/\[](\d+\.\d+)(?:】|/次|\])", mid)
                sort_p = float(m2.group(1)) if m2 else 0.25
                disp_p = f"${sort_p}/次" if m2 else "站内计费"
            st = stats.get(f"{pid}::{mid}", {"ok": 0, "fail": 0, "last_ms": 0})
            tot = st["ok"] + st["fail"]
            rate = round(st["ok"] * 100.0 / tot, 1) if tot > 0 else None
            sub_list.append({
                "provider_id": pid,
                "provider_name": p["name"],
                "model": mid,
                "sort_price": sort_p,
                "display_price": disp_p,
                "desc": p_info.get("description", ""),
                "rate": rate,
                "last_ms": st["last_ms"],
                "in_basket": f"{pid}::{mid}" in basket_keys
            })
        return sub_list

    lists = await asyncio.gather(*(fetch_p(p) for p in PROVIDERS))
    for l in lists:
        catalog.extend(l)
    catalog.sort(key=lambda x: (x["sort_price"], x["provider_id"], x["model"]))
    return {"total": len(catalog), "models": catalog[:150]}


@app.get("/", response_class=HTMLResponse)
@app.get("/panel", response_class=HTMLResponse)
async def web_hub_page():
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>阿斯特雷亚 · 24h云端粮草总管</title>
<style>
  :root { --bg:#f5f7fb; --card:#fff; --pri:#c83e3b; --pri-s:#fceceb; --acc:#4f46e5; --acc-s:#eef2ff; --grn:#16a34a; --grn-s:#dcfce7; --amb:#d97706; --amb-s:#fef3c7; --txt:#1e293b; --sub:#64748b; --bdr:#e2e8f0; }
  * { box-sizing:border-box; margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }
  body { background:var(--bg); color:var(--txt); padding:14px; max-width:560px; margin:0 auto; display:flex; flex-direction:column; gap:12px; }
  .top { background:var(--card); border-radius:20px; padding:16px; border:1px solid var(--bdr); box-shadow:0 4px 14px rgba(0,0,0,0.03); }
  .meta { font-size:11px; color:var(--sub); }
  .h-row { display:flex; justify-content:space-between; align-items:center; margin:4px 0 12px; }
  .h-title { font-size:18px; font-weight:800; }
  .pill { font-size:11px; padding:3px 9px; border-radius:99px; background:var(--grn-s); color:var(--grn); font-weight:600; }
  .btns { display:flex; gap:8px; flex-wrap:wrap; }
  .btn { border:none; padding:8px 13px; border-radius:99px; font-size:12px; font-weight:600; cursor:pointer; background:var(--pri); color:#fff; white-space:nowrap; }
  .btn.sec { background:var(--acc-s); color:var(--acc); }
  .btn.grn { background:var(--grn-s); color:var(--grn); }
  .btn.amb { background:var(--amb-s); color:var(--amb); }
  .tabs { display:flex; gap:6px; background:#e2e8f0; padding:4px; border-radius:12px; }
  .tab { flex:1; border:none; background:transparent; padding:9px 4px; border-radius:9px; font-size:12px; font-weight:700; color:var(--sub); cursor:pointer; }
  .tab.active { background:var(--card); color:var(--pri); box-shadow:0 2px 6px rgba(0,0,0,0.05); }
  .sec { display:none; flex-direction:column; gap:10px; }
  .sec.active { display:flex; }
  .w-card { background:var(--card); border-radius:18px; padding:14px 16px; border:1px solid var(--bdr); display:flex; flex-direction:column; gap:8px; }
  .w-box { display:flex; justify-content:space-between; align-items:baseline; background:#f8fafc; padding:10px 12px; border-radius:12px; }
  .w-bal { font-size:20px; font-weight:800; color:var(--pri); cursor:pointer; }
  .m-card { background:var(--card); border:1px solid var(--bdr); border-radius:14px; padding:11px 13px; display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .m-card.pri { border:2px solid var(--pri); background:#fffafa; }
  .m-info { flex:1; min-width:0; }
  .m-title { font-size:12px; font-weight:700; word-break:break-all; line-height:1.35; }
  .tags { display:flex; gap:5px; flex-wrap:wrap; margin-top:4px; }
  .tag { font-size:10px; padding:2px 7px; border-radius:6px; font-weight:600; background:#f1f5f9; color:var(--sub); }
  .tag.p { background:var(--pri-s); color:var(--pri); }
  .tag.r { background:var(--grn-s); color:var(--grn); }
  .act-col { display:flex; gap:5px; flex-shrink:0; align-items:center; }
  .s-bar { display:flex; gap:6px; background:var(--card); padding:8px; border-radius:12px; border:1px solid var(--bdr); }
  .s-inp { flex:1; border:1px solid var(--bdr); border-radius:8px; padding:7px 10px; font-size:12px; outline:none; }
  .log { background:#f1f5f9; padding:10px 12px; border-radius:12px; font-size:11px; color:var(--sub); white-space:pre-wrap; line-height:1.4; }
</style>
</head>
<body>
<div class="top">
  <div class="meta">REINHARD 24/7 CLOUD HUB (43.108.90.138) · 同步时间 <span id="t-span">--:--:--</span></div>
  <div class="h-row">
    <span class="h-title">⚔️ 云端粮草总管 6.0</span>
    <span class="pill">Ubuntu 24h永不掉线</span>
  </div>
  <div class="btns">
    <button class="btn" onclick="loadDash(1)">🔄 刷新状态与余额</button>
    <button class="btn grn" onclick="runCheckin()">🎁 一键四站签到</button>
  </div>
</div>

<div class="tabs">
  <button id="t-wallet" class="tab active" onclick="sw('wallet')">💰 四站实时余额</button>
  <button id="t-basket" class="tab" onclick="sw('basket')">🛒 常用备用池</button>
  <button id="t-shop" class="tab" onclick="sw('shop')">🏪 全站价格榜</button>
  <button id="t-ledger" class="tab" onclick="sw('ledger')">📜 消费账单</button>
</div>

<div id="sec-wallet" class="sec active"></div>
<div id="sec-basket" class="sec"></div>
<div id="sec-shop" class="sec">
  <div class="s-bar">
    <input id="q-inp" class="s-inp" value="gemini-4-argon" placeholder="搜索模型（如 gemini-4-argon / claude）">
    <button class="btn" onclick="loadShop()">🔍 实时搜索</button>
  </div>
  <div id="shop-box" style="display:flex;flex-direction:column;gap:8px;"></div>
</div>
<div id="sec-ledger" class="sec"></div>

<div id="log" class="log">✨ 已部署在首尔 Ubuntu 云服务器 (43.108.90.138:8788)，无需开电脑，全球 5G/Wi-Fi 永久直连！每次聊天自动按定价扣减对应站子余额。</div>

<script>
let currentBasket = [];
let currentShop = [];

function sw(k) {
  ['wallet','basket','shop','ledger'].forEach(x => {
    document.getElementById('t-'+x).classList.toggle('active', x===k);
    document.getElementById('sec-'+x).classList.toggle('active', x===k);
  });
  if (k==='shop' && !currentShop.length) loadShop();
}

async function editBal(id, name, cur) {
  const val = prompt(`校准【${name}】当前总额度（之后每次调用将在此基础上自动实时扣减）：`, cur);
  if (!val) return;
  await fetch('/hub/wallet_set', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, balance:val.trim()}) });
  loadDash(0);
}

async function loadDash(ref=0) {
  try {
    const r = await fetch('/hub/dashboard?refresh=' + ref);
    const d = await r.json();
    document.getElementById('t-span').innerText = d.updated_at;

    const wBox = document.getElementById('sec-wallet');
    wBox.innerHTML = '';
    (d.wallets || []).forEach(w => {
      const el = document.createElement('div');
      el.className = 'w-card';
      el.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <b style="font-size:15px;">${w.name}</b>
          <span class="pill">${w.online ? '🟢 云端直连在线' : '🔴 离线'}</span>
        </div>
        <div class="w-box">
          <div style="font-size:11px;color:var(--sub);">
            <div>今日消耗: ${w.today_used || '-'}</div>
            <div style="margin-top:2px;">累计消耗: ${w.total_used || '-'} · 调用: ${w.requests || '-'}次</div>
          </div>
          <div class="w-bal" onclick="editBal('${w.id}','${w.name}','${w.balance}')" title="点击可手动校准初始余额">${w.balance} ✎</div>
        </div>
        <div style="font-size:11px;color:var(--grn);font-weight:600;">📅 ${w.checkin || ''}</div>
      `;
      wBox.appendChild(el);
    });

    currentBasket = d.basket || [];
    renderBasket();

    const lBox = document.getElementById('sec-ledger');
    lBox.innerHTML = '';
    (d.ledger || []).forEach(item => {
      const el = document.createElement('div');
      el.className = 'm-card';
      el.innerHTML = `
        <div class="m-info">
          <div class="m-title">[${item.time} @ ${item.room}] ${item.model}</div>
          <div class="tags">
            <span class="tag">${item.provider_name}</span>
            <span class="tag p">${item.price_label}</span>
            <span class="tag r">${item.ok ? '✅ HTTP 200 · '+item.ms+'ms' : '❌ HTTP '+item.status+' · '+item.ms+'ms'}</span>
          </div>
        </div>
      `;
      lBox.appendChild(el);
    });
  } catch (e) {}
}

function renderBasket() {
  const bBox = document.getElementById('sec-basket');
  bBox.innerHTML = '';
  currentBasket.forEach((b, i) => {
    const el = document.createElement('div');
    el.className = 'm-card' + (b.is_primary ? ' pri' : '');
    const rateTxt = b.rate !== null ? `成功率 ${b.rate}% (成${b.ok}/败${b.fail})` : '被动统计中';
    el.innerHTML = `
      <div class="m-info" onclick="copyModel(${i}, 'basket')">
        <div class="m-title">${b.is_primary ? '👑 [主力] ' : `#${i+1} `}${b.model}</div>
        <div class="tags">
          <span class="tag">${b.provider_name}</span>
          <span class="tag p">💰 ${b.display_price}</span>
          <span class="tag r">📊 ${rateTxt}</span>
        </div>
      </div>
      <div class="act-col">
        ${!b.is_primary ? `<button class="btn" onclick="basketAction('set_primary', ${i}, 'basket')">设主力</button>` : `<button class="btn grn">主力中</button>`}
        <button class="btn amb" onclick="basketAction('remove', ${i}, 'basket')">🗑️删除</button>
      </div>
    `;
    bBox.appendChild(el);
  });
}

function copyModel(idx, source) {
  const item = source === 'basket' ? currentBasket[idx] : currentShop[idx];
  if (!item) return;
  navigator.clipboard?.writeText(item.model).catch(()=>{});
  document.getElementById('log').innerText = "📋 已复制模型名：" + item.model;
}

async function basketAction(action, idx, source) {
  const item = source === 'basket' ? currentBasket[idx] : currentShop[idx];
  if (!item) return;
  const payload = {
    action,
    provider_id: item.provider_id,
    provider_name: item.provider_name,
    model: item.model,
    display_price: item.display_price,
    unit_cost: item.unit_cost || item.sort_price || 0.20
  };
  const r = await fetch('/hub/basket', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  const d = await r.json();
  if (d.basket) {
    currentBasket = d.basket;
    renderBasket();
    if (currentShop.length) renderShop();
  }
  const log = document.getElementById('log');
  if (action === 'add') log.innerText = `➕ 已将【${item.model}】加入常用备用池！`;
  else if (action === 'remove') log.innerText = `🗑️ 已将【${item.model}】从备用池删除。`;
  else if (action === 'set_primary') log.innerText = `👑 已将【${item.provider_name} · ${item.model}】设为首选主力！`;
}

async function loadShop() {
  const q = document.getElementById('q-inp').value.trim();
  const box = document.getElementById('shop-box');
  box.innerHTML = '<div class="log">正在请求四站公开价格表...</div>';
  const r = await fetch('/hub/catalog?q=' + encodeURIComponent(q));
  const d = await r.json();
  currentShop = d.models || [];
  renderShop();
}

function renderShop() {
  const box = document.getElementById('shop-box');
  box.innerHTML = '';
  const basketKeys = new Set(currentBasket.map(b => b.provider_id + '::' + b.model));
  currentShop.forEach((m, i) => {
    const inB = basketKeys.has(m.provider_id + '::' + m.model);
    const el = document.createElement('div');
    el.className = 'm-card';
    el.innerHTML = `
      <div class="m-info" onclick="copyModel(${i}, 'shop')">
        <div class="m-title">${m.model}</div>
        <div class="tags">
          <span class="tag">${m.provider_name}</span>
          <span class="tag p">💰 ${m.display_price}</span>
          ${m.desc ? `<span class="tag">${m.desc}</span>` : ''}
        </div>
      </div>
      <div class="act-col">
        <button class="btn ${inB ? 'grn' : 'sec'}" onclick="basketAction('add', ${i}, 'shop')">${inB ? '✓已在池' : '➕加入备选池'}</button>
        <button class="btn" onclick="basketAction('set_primary', ${i}, 'shop')">直用</button>
      </div>
    `;
    box.appendChild(el);
  });
}

async function runCheckin() {
  const log = document.getElementById('log');
  log.innerText = "🎁 正在执行四站云端签到...";
  await fetch('/hub/checkin', { method:'POST' });
  loadDash(1);
  log.innerText = "🎁 四站签到与状态刷新完成！";
}

loadDash(0);
</script>
</body>
</html>"""
    return HTMLResponse(html)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    raw_path = path.lstrip("/")
    prov_map = {p["id"]: p for p in PROVIDERS}
    client = get_http_client()

    clean_path = raw_path.lstrip("/")
    while clean_path.startswith("v1/v1/"):
        clean_path = clean_path[3:]
    if not clean_path.startswith("v1/"):
        clean_path = f"v1/{clean_path}"

    if request.method == "GET" and clean_path == "v1/models":
        basket = load_basket()
        seen = set()
        models_out = []
        for b in basket:
            if b["model"] not in seen:
                seen.add(b["model"])
                models_out.append({"id": b["model"], "object": "model", "owned_by": b["provider_name"]})
        for pid in ("taleapi", "blacknoir"):
            p = prov_map.get(pid)
            if not p:
                continue
            try:
                r = await client.get(f"{p['base_url'].rstrip('/')}/v1/models", headers={"Authorization": f"Bearer {p['api_key']}"}, timeout=5.0)
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        mid = m.get("id")
                        if mid and mid not in seen:
                            seen.add(mid)
                            models_out.append(m)
            except Exception:
                pass
        return JSONResponse({"object": "list", "data": models_out})

    body_bytes = await request.body()
    is_stream = False
    room = "Aru"
    payload = {}

    if request.method == "POST" and clean_path.endswith("chat/completions"):
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            is_stream = bool(payload.get("stream", False))
            messages = payload.get("messages", [])
            room = detect_room(messages, request.headers.get("user-agent", ""))
            records = load_hot_memory()

            hot_text = build_hot_injection(room, records)
            if hot_text and messages:
                injected = False
                for m in messages:
                    if m.get("role") in ("system", "developer"):
                        if isinstance(m.get("content"), str):
                            m["content"] += hot_text
                            injected = True
                            break
                        elif isinstance(m.get("content"), list):
                            m["content"].append({"type": "text", "text": hot_text})
                            injected = True
                            break
                if not injected:
                    messages.insert(0, {"role": "system", "content": hot_text})

            last_user_msg = ""
            prev_assistant_msg = ""
            for m in reversed(messages):
                if not last_user_msg and m.get("role") == "user":
                    txt = clean_user_text(extract_plain_text(m.get("content", "")))
                    if txt and not txt.startswith("Images returned by the completed tool calls"):
                        last_user_msg = txt[:300]
                elif last_user_msg and not prev_assistant_msg and m.get("role") == "assistant":
                    txt = extract_plain_text(m.get("content", ""))
                    if txt:
                        prev_assistant_msg = txt[:300]
                        break

            if last_user_msg:
                now_str = datetime.now().strftime("%m-%d %H:%M")
                if not records or records[-1].get("user") != last_user_msg:
                    records.append({
                        "time": now_str,
                        "room": room,
                        "user": last_user_msg,
                        "assistant": prev_assistant_msg
                    })
                    save_hot_memory(records)
        except Exception as e:
            print(f"[Gateway Warning] {e}")

    basket = load_basket()
    candidates = []
    for b in basket:
        if b["provider_id"] in prov_map:
            candidates.append((prov_map[b["provider_id"]], b["model"], float(b.get("unit_cost", 0.15)), b.get("display_price", "$0.15/次")))

    last_error = None
    for idx, (prov, target_model, unit_cost, disp_price) in enumerate(candidates):
        target_url = f"{prov['base_url'].rstrip('/')}/{clean_path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        if payload:
            payload["model"] = target_model
            req_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        else:
            req_bytes = body_bytes

        forward_headers = {
            "Content-Type": "application/json",
            "Accept": request.headers.get("accept", "*/*"),
            "Authorization": f"Bearer {prov['api_key']}"
        }

        t0 = time.time()
        try:
            if is_stream:
                req = client.build_request(request.method, target_url, headers=forward_headers, content=req_bytes)
                r = await client.send(req, stream=True)
                ms = int((time.time() - t0) * 1000)

                if r.status_code in (400, 401, 403, 404, 429, 500, 502, 503, 504) and idx < len(candidates) - 1:
                    record_stat(prov["id"], target_model, False, ms, r.status_code)
                    append_ledger({
                        "time": datetime.now().strftime("%m-%d %H:%M:%S"),
                        "room": room,
                        "provider_id": prov["id"],
                        "provider_name": prov["name"],
                        "model": target_model,
                        "cost_usd": 0.0,
                        "price_label": "失败秒切下一条",
                        "ms": ms,
                        "ok": False,
                        "status": r.status_code
                    })
                    await r.aclose()
                    continue

                record_stat(prov["id"], target_model, r.status_code == 200, ms, r.status_code)
                append_ledger({
                    "time": datetime.now().strftime("%m-%d %H:%M:%S"),
                    "room": room,
                    "provider_id": prov["id"],
                    "provider_name": prov["name"],
                    "model": target_model,
                    "cost_usd": unit_cost if r.status_code == 200 else 0.0,
                    "price_label": disp_price,
                    "ms": ms,
                    "ok": r.status_code == 200,
                    "status": r.status_code
                })

                async def stream_gen(resp_obj=r):
                    collected = []
                    try:
                        async for chunk in resp_obj.aiter_bytes():
                            yield chunk
                            try:
                                text_chunk = chunk.decode("utf-8", errors="ignore")
                                for line in text_chunk.splitlines():
                                    if line.startswith("data: ") and line != "data: [DONE]":
                                        data_obj = json.loads(line[6:])
                                        delta = data_obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if delta:
                                            collected.append(delta)
                            except Exception:
                                pass
                    finally:
                        await resp_obj.aclose()
                        if collected:
                            full_reply = "".join(collected).strip()
                            if "</think>" in full_reply:
                                full_reply = full_reply.split("</think>")[-1].strip()
                            if full_reply:
                                records = load_hot_memory()
                                if records:
                                    records[-1]["assistant"] = full_reply[:300]
                                    save_hot_memory(records)

                resp_headers = {
                    k: v for k, v in r.headers.items()
                    if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
                }
                return StreamingResponse(stream_gen(), status_code=r.status_code, headers=resp_headers)

            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=req_bytes
            )
            ms = int((time.time() - t0) * 1000)
            if resp.status_code in (400, 401, 403, 404, 429, 500, 502, 503, 504) and idx < len(candidates) - 1:
                record_stat(prov["id"], target_model, False, ms, resp.status_code)
                append_ledger({
                    "time": datetime.now().strftime("%m-%d %H:%M:%S"),
                    "room": room,
                    "provider_id": prov["id"],
                    "provider_name": prov["name"],
                    "model": target_model,
                    "cost_usd": 0.0,
                    "price_label": "失败秒切下一条",
                    "ms": ms,
                    "ok": False,
                    "status": resp.status_code
                })
                continue

            record_stat(prov["id"], target_model, resp.status_code == 200, ms, resp.status_code)
            append_ledger({
                "time": datetime.now().strftime("%m-%d %H:%M:%S"),
                "room": room,
                "provider_id": prov["id"],
                "provider_name": prov["name"],
                "model": target_model,
                "cost_usd": unit_cost if resp.status_code == 200 else 0.0,
                "price_label": disp_price,
                "ms": ms,
                "ok": resp.status_code == 200,
                "status": resp.status_code
            })

            if request.method == "POST" and clean_path.endswith("chat/completions"):
                try:
                    res_json = resp.json()
                    reply_txt = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if reply_txt:
                        records = load_hot_memory()
                        if records:
                            records[-1]["assistant"] = str(reply_txt).strip()[:300]
                            save_hot_memory(records)
                except Exception:
                    pass

            resp_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
            }
            return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)
        except Exception as exc:
            ms = int((time.time() - t0) * 1000)
            record_stat(prov["id"], target_model, False, ms, 500)
            last_error = exc
            if idx < len(candidates) - 1:
                continue

    return Response(
        content=json.dumps({"error": {"message": f"All Basket Pool models failed. Last error: {last_error}"}}, ensure_ascii=False),
        status_code=502,
        media_type="application/json"
    )
