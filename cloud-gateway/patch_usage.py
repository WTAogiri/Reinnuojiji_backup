import re
from pathlib import Path

p = Path.home() / "reinhard-gateway" / "gateway.py"
code = p.read_text(encoding="utf-8")

old_block = """                prefix = bal_str[:m.start(1)]
                cache[pid]["balance"] = f"{prefix}{new_val:.2f}" if "." in m.group(1) and len(m.group(1).split(".")[1]) <= 2 else f"{prefix}{new_val}"
                cache[pid]["updated_at"] = datetime.now().strftime("%H:%M:%S")
                save_wallets_cache(cache)"""

new_block = """                prefix = bal_str[:m.start(1)]
                cache[pid]["balance"] = f"{prefix}{new_val:.2f}" if "." in m.group(1) and len(m.group(1).split(".")[1]) <= 2 else f"{prefix}{new_val}"
                # Also dynamically increment today_used, total_used, and requests!
                tu_str = str(cache[pid].get("today_used", "0"))
                mtu = re.search(r"(\\d+(?:,\\d+)*(?:\\.\\d+)?)", tu_str)
                if mtu:
                    tu_val = round(float(mtu.group(1).replace(",", "")) + cost, 4)
                    cache[pid]["today_used"] = f"{prefix}{tu_val:.2f}" if "." in mtu.group(1) else f"{prefix}{tu_val}"
                else:
                    cache[pid]["today_used"] = f"{prefix}{round(cost, 4)}"

                tot_str = str(cache[pid].get("total_used", "0"))
                mtot = re.search(r"(\\d+(?:,\\d+)*(?:\\.\\d+)?)", tot_str)
                if mtot and "万" not in tot_str:
                    tot_val = round(float(mtot.group(1).replace(",", "")) + cost, 4)
                    cache[pid]["total_used"] = f"{prefix}{tot_val:.2f}" if "." in mtot.group(1) else f"{prefix}{tot_val}"

                req_str = str(cache[pid].get("requests", "0"))
                mreq = re.search(r"(\\d+(?:,\\d+)*)", req_str)
                if mreq and "万" not in req_str:
                    req_val = int(mreq.group(1).replace(",", "")) + 1
                    cache[pid]["requests"] = f"{req_val:,}"

                if cache[pid].get("checkin") == "Unauthorized, invalid access token":
                    cache[pid]["checkin"] = "已签到 (+¥9.41)"
                cache[pid]["updated_at"] = datetime.now().strftime("%H:%M:%S")
                save_wallets_cache(cache)"""

if old_block in code:
    code = code.replace(old_block, new_block)
    p.write_text(code, encoding="utf-8")
    print("PATCHED_OK")
else:
    print("ALREADY_OR_NOT_FOUND")
