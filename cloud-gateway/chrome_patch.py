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

app = FastAPI(title="Reinhard Cloud Hub 6.1 (24/7 VPS + Chrome Bridge)")

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
CHROME_DEBUG_URL = "http://127.0.0.1:9223"
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
        "domain_kw": "taleapi.asia",
        "base_url": "https://api.taleapi.asia",
        "overview_url": "https://taleapi.asia/dashboard/overview",
        "checkin_url": "https://taleapi.asia/profile",
        "pricing_url": "https://api.taleapi.asia/api/pricing",
        "api_key": "sk-egBV2II62B2iGCmNNCoVQKXHa3k3YphkMZ5yQYIccJBuM9Bf"
    },
    {
        "id": "blacknoir",
        "name": "Noir API",
        "domain_kw": "blacknoir.cn",
        "base_url": "https://noir.blacknoir.cn",
        "overview_url": "https://noir.blacknoir.cn/dashboard/overview",
        "checkin_url": "https://noir.blacknoir.cn/profile",
        "pricing_url": "https://noir.blacknoir.cn/api/pricing",
        "api_key": "sk-RTnNoazyLTvKgUsUuYaCO5HGDCfxLBNuD05ChX1yJsxkOFCN"
    },
    {
        "id": "molibingcha",
        "name": "茉莉冰茶",
        "domain_kw": "45.205.31.214",
        "base_url": "http://b.molibingcha.xyz",
        "overview_url": "http://45.205.31.214/profile",
        "checkin_url": "http://45.205.31.214/checkin",
        "pricing_url": "http://45.205.31.214/api/pricing",
        "api_key": "sk-yh7YjLo6y7kbyXKbhLZzLCLMiq18kxnOSkNfBCA5eU79RwDt"
    },
    {
        "id": "gemai",
        "name": "哈基米 (GemAI)",
        "domain_kw": "gemai.cc",
        "base_url": "https://api.gemai.cc",
        "overview_url": "https://api.gemai.cc/profile",
        "checkin_url": "https://api.gemai.cc/profile",
        "pricing_url": "https://api.gemai.cc/api/pricing",
        "api_key": "sk-55AtPJ3CuM1UDJONuSyS9AL6UGXk7uscYnBMiWSWmWo9tlNT"
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
        "gateway": "Reinhard Cloud Hub 6.1 (24/7 VPS + Chrome Bridge)",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "basket_count": len(load_basket()),
        "hot_records": len(load_hot_memory())
    }


@app.get("/chrome/tabs")
async def chrome_tabs():
    client = get_http_client()
    r = await client.get(f"{CHROME_DEBUG_URL}/json/list", timeout=5.0)
    return r.json()


@app.post("/chrome/eval")
async def chrome_eval(request: Request):
    import websockets
    body = await request.json()
    expr = body.get("expression", "document.title + ' | ' + location.href + '\\n' + document.body.innerText.slice(0, 4000)")
    target_url = body.get("url")
    tab_index = int(body.get("tab_index", 0))

    client = get_http_client()
    tabs = (await client.get(f"{CHROME_DEBUG_URL}/json/list", timeout=5.0)).json()
    page_tabs = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith("chrome://")]
    if not page_tabs:
        page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        return {"status": "error", "message": "No open page tabs found in Chrome"}
    tab = page_tabs[min(tab_index, len(page_tabs) - 1)]
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        return {"status": "error", "message": "No webSocketDebuggerUrl on tab", "tab": tab}

    async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
        msg_id = 1
        if target_url:
            await ws.send(json.dumps({"id": msg_id, "method": "Page.navigate", "params": {"url": target_url}}))
            await ws.recv()
            msg_id += 1
            await asyncio.sleep(float(body.get("wait", 2.5)))

        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True
            }
        }))
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                return {"status": "ok", "tab": {"title": tab.get("title"), "url": tab.get("url")}, "result": data.get("result")}
