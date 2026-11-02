import re
from pathlib import Path

p = Path.home() / "reinhard-gateway" / "gateway.py"
code = p.read_text(encoding="utf-8")

real_sync_code = '''
LIVE_SESSIONS = {
    "blacknoir": {"type": "refresh", "url": "https://noir.blacknoir.cn", "uid": "15878", "symbol": "¥", "cookie": "ea71a22b-58b0-449d-aa4d-4a2d2a256e00.f1cf3ff1137ca77eac3377ca4ae3c14795b1c78c90f47c61589614574bc3c347"},
    "molibingcha": {"type": "refresh", "url": "http://45.205.31.214", "uid": "1004846", "symbol": "❄️ ", "cookie": "dab05c30-faf1-40d9-a5b4-949c8191df82.VrMO8aWv1TDBmG67N6IBDTgkizGIuIOyxoqAKYvbcUMdor7dkF9QGXhq9NZxhhsw"},
    "gemai": {"type": "session", "url": "https://api.gemai.cc", "uid": "197863", "symbol": "¥", "cookie": "MTc5MzUyODIxN3xEWDhFQVFMX2dBQUJFQUVRQUFEX3ZmLUFBQVlHYzNSeWFXNW5EQVlBQkhKdmJHVURhVzUwQkFJQUFnWnpkSEpwYm1jTUNBQUdjM1JoZEhWekEybHVkQVFDQUFJR2MzUnlhVzVuREFjQUJXZHliM1Z3Qm5OMGNtbHVad3dKQUFka1pXWmhkV3gwQm5OMGNtbHVad3dTQUJCelpXTjFjbWwwZVY5MlpYSnphVzl1QldsdWREWTBCQUlBQUFaemRISnBibWNNQkFBQ2FXUURhVzUwQkFVQV9RWUp6Z1p6ZEhKcGJtY01DZ0FJZFhObGNtNWhiV1VHYzNSeWFXNW5EQTRBRE9haXAtYWhrT2FXcmVpbmtnPT18izSNJDUuQH0Iqgg3zHHOxJ_A53ubiryrhgbbuJKhBLs="}
}

async def sync_real_station_api(pid: str, w: dict, client: httpx.AsyncClient):
    cfg = LIVE_SESSIONS.get(pid)
    if not cfg:
        return w
    try:
        now = int(time.time())
        start_day = now - ((now + 8 * 3600) % 86400)
        sym = cfg["symbol"]
        if cfg["type"] == "refresh":
            r = await client.post(
                f"{cfg['url']}/api/user/auth/refresh",
                headers={"Cookie": f"new_api_refresh={cfg['cookie']}", "User-Agent": "Mozilla/5.0"},
                timeout=5.0
            )
            if r.status_code == 200:
                d = r.json().get("data", {})
                user = d.get("user", {})
                token = d.get("access_token", "")
                if user:
                    w["balance"] = f"{sym}{float(user.get('quota', 0)) / 500000:.2f}"
                    w["total_used"] = f"{sym}{float(user.get('used_quota', 0)) / 500000:.2f}"
                    w["requests"] = f"{int(user.get('request_count', 0)):,}"
                    w["online"] = True
                if token:
                    dr = await client.get(
                        f"{cfg['url']}/api/data/self?start_timestamp={start_day}&end_timestamp={now}",
                        headers={"Authorization": f"Bearer {token}", "New-Api-User": cfg["uid"]},
                        timeout=5.0
                    )
                    if dr.status_code == 200:
                        items = dr.json().get("data") or []
                        t_used = sum(float(x.get("quota", 0)) for x in items) / 500000
                        w["today_used"] = f"{sym}{t_used:.2f}"
        elif cfg["type"] == "session":
            r = await client.get(
                f"{cfg['url']}/api/user/self",
                headers={"Cookie": f"session={cfg['cookie']}", "New-Api-User": cfg["uid"]},
                timeout=5.0
            )
            if r.status_code == 200:
                user = r.json().get("data", {})
                if user:
                    q = float(user.get("total_quota") or user.get("quota") or 0) / 500000
                    u = float(user.get("used_quota") or 0) / 500000
                    w["balance"] = f"{sym}{q:,.2f}"
                    w["total_used"] = f"{sym}{u:,.1f}"
                    w["requests"] = f"{int(user.get('request_count', 0)):,}"
                    w["online"] = True
    except Exception:
        pass
    return w
'''

if "LIVE_SESSIONS =" not in code:
    code = code.replace("@app.get(\"/hub/dashboard\")", real_sync_code + "\n\n@app.get(\"/hub/dashboard\")")
    old_ping = '''                r = await client.get(f"{p['base_url'].rstrip('/')}/v1/models", headers={"Authorization": f"Bearer {p['api_key']}"}, timeout=5.0)
                w["online"] = (r.status_code == 200)
                w["updated_at"] = datetime.now().strftime("%H:%M:%S")'''
    new_ping = '''                r = await client.get(f"{p['base_url'].rstrip('/')}/v1/models", headers={"Authorization": f"Bearer {p['api_key']}"}, timeout=5.0)
                w["online"] = (r.status_code == 200)
                w = await sync_real_station_api(pid, w, client)
                w["updated_at"] = datetime.now().strftime("%H:%M:%S")'''
    code = code.replace(old_ping, new_ping)
    p.write_text(code, encoding="utf-8")
    print("REAL_API_SYNC_INSTALLED")
else:
    print("ALREADY_INSTALLED")
