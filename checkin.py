#!/usr/bin/env python3
"""米游社每日签到（GitHub Actions 版）

环境变量:
  COOKIE_JSON_B64  cookie.json 的 base64（存仓库 Secret）
  GITHUB_REPOSITORY 由 Actions 注入，用于生成页面标题（可选）

产出:
  history.json     累计签到记录
  docs/index.html  静态看板（GitHub Pages）
"""
import base64, json, os, random, hashlib, ssl, sys, time
import urllib.request, urllib.error, urllib.parse

APP_VERSION = "2.117.0"
UA = ("Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/" + APP_VERSION)
SALT_X6 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"

GAMES = {
    "hk4e_cn": ("原神", "e202311201442471", "https://api-takumi.mihoyo.com", "/event/luna"),
    "hkrpg_cn": ("崩坏：星穹铁道", "e202304121516551", "https://api-takumi.mihoyo.com", "/event/luna"),
    "nap_cn": ("绝区零", "e202406242138391", "https://act-nap-api.mihoyo.com", "/event/luna/zzz"),
    "bh3_cn": ("崩坏3", "e202306201626331", "https://api-takumi.mihoyo.com", "/event/luna"),
    "bh2_cn": ("崩坏2", "e202203291431091", "https://api-takumi.mihoyo.com", "/event/luna"),
    "nxx_cn": ("未定事件簿", "e202202251749321", "https://api-takumi.mihoyo.com", "/event/luna"),
}
SIGNGAME = {"hk4e_cn": "hk4e", "hkrpg_cn": "hkrpg", "nap_cn": "zzz",
            "bh3_cn": "bh3", "bh2_cn": "bh2", "nxx_cn": "nxx"}
BINDING_URL = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie"
CTX = ssl.create_default_context()


def mask(s):
    s = str(s or "")
    return (s[0] + "***") if len(s) > 1 else s


def mask_uid(u):
    u = str(u or "")
    return (u[:3] + "****" + u[-2:]) if len(u) > 7 else u


def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def ds2(query="", body=""):
    t = str(int(time.time()))
    r = str(random.randint(100001, 200000))
    return f"{t},{r},{md5(f'salt={SALT_X6}&t={t}&r={r}&b={body}&q={query}')}"


def load_account():
    raw = os.environ.get("COOKIE_JSON_B64")
    if raw:
        data = json.loads(base64.b64decode(raw))
    else:
        with open("cookie.json") as f:
            data = json.load(f)
    cookie = ";".join(f"{k}={v}" for k, v in (data.get("cookies") or {}).items())
    dev = data.get("device") or ("8" + md5(cookie)[:15])
    return cookie, dev


def request(url, cookie, dev, body=None, query="", signgame=None):
    headers = {
        "Cookie": cookie, "DS": ds2(query, body or ""),
        "x-rpc-app_version": APP_VERSION, "x-rpc-client_type": "5",
        "x-rpc-channel": "miyousheluodi", "x-rpc-device_id": dev,
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Origin": "https://webstatic.mihoyo.com", "Referer": "https://webstatic.mihoyo.com/",
    }
    if signgame:
        headers["x-rpc-signgame"] = signgame
    data = body.encode() if isinstance(body, str) else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"retcode": e.code, "message": e.read().decode("utf-8", "replace")[:200]}
    except Exception as e:
        return {"retcode": -9999, "message": f"网络错误 {e}"}


def main():
    print("run at", time.strftime("%Y-%m-%d %H:%M:%S"))
    cookie, dev = load_account()
    records = []
    for biz in GAMES:
        name, act_id, host, prefix = GAMES[biz]
        q = urllib.parse.urlencode({"game_biz": biz, "lang": "zh-cn"})
        roles = (request(BINDING_URL + "?" + q, cookie, dev, query=q).get("data") or {}).get("list") or []
        if not roles:
            continue
        qa = urllib.parse.urlencode({"act_id": act_id, "lang": "zh-cn"})
        awards = (request(host + prefix + "/home?" + qa, cookie, dev, query=qa,
                          signgame=SIGNGAME[biz]).get("data") or {}).get("awards") or []
        for role in roles:
            uid, region = str(role["game_uid"]), role["region"]
            nick = role.get("nickname", "")
            body = json.dumps({"act_id": act_id, "region": region, "uid": uid, "lang": "zh-cn"},
                              separators=(",", ":"))
            res = request(host + prefix + "/sign", cookie, dev, body=body, signgame=SIGNGAME[biz])
            rc = res.get("retcode")
            if rc not in (0, -5003):
                print(f"[FAIL] {name} {mask(nick)} {rc} {res.get('message')}")
                records.append({"date": time.strftime("%Y-%m-%d"), "game": name, "nick": mask(nick),
                                "uid": mask_uid(uid), "ok": False, "error": f"{rc} {res.get('message')}"})
                continue
            time.sleep(random.randint(2, 4))
            qi = urllib.parse.urlencode({"act_id": act_id, "region": region, "uid": uid, "lang": "zh-cn"})
            info = request(host + prefix + "/info?" + qi, cookie, dev, query=qi,
                           signgame=SIGNGAME[biz]).get("data") or {}
            day = int(info.get("total_sign_day") or 0)
            award = ""
            if awards and 0 < day <= len(awards):
                a = awards[day - 1]
                award = f"{a.get('name')}×{a.get('cnt')}"
            ok = bool(info.get("is_sign"))
            print(f"[{'OK' if ok else 'NG'}] {name} {mask(nick)} 第{day}天 {award}")
            records.append({"date": time.strftime("%Y-%m-%d"), "game": name, "nick": mask(nick),
                            "uid": mask_uid(uid), "ok": ok, "day": day, "award": award,
                            "signed_now": rc == 0})

    try:
        with open("history.json") as f:
            hist = json.load(f)
    except Exception:
        hist = []
    today = time.strftime("%Y-%m-%d")
    hist = [h for h in hist if h.get("date") != today]
    hist.extend(records)
    with open("history.json", "w") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    build_page(hist)
    if any(r.get("ok") for r in records):
        return 0
    print("no role signed / cookie may be invalid")
    return 1


CSS = """
*{box-sizing:border-box}body{margin:0;padding:16px 14px 40px;font:15px/1.6 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;background:#0f1216;color:#e8eaed}
h1{font-size:19px;margin:0 0 4px}.sub{color:#8b939d;font-size:12px;margin-bottom:16px}
.card{background:#171b21;border:1px solid #232a33;border-radius:14px;padding:14px;margin-bottom:12px}
.game{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.name{font-weight:600;font-size:16px}.nick{color:#8b939d;font-size:12px}
.big{font-size:26px;font-weight:700;color:#7dd3a0}.big span{font-size:13px;color:#8b939d;font-weight:400;margin-left:4px}
.award{margin-top:6px;color:#e8c46a;font-size:14px}
.row{display:flex;justify-content:space-between;padding:6px 0;border-top:1px solid #232a33;font-size:13px}
.row:first-of-type{border-top:none}.d{color:#8b939d}.a{color:#cfd4da}
.foot{margin-top:18px;color:#5f6873;font-size:11px;text-align:center}
"""


def build_page(hist):
    os.makedirs("docs", exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    games = {}
    for h in hist:
        games.setdefault(h.get("game", "?"), []).append(h)
    cards = []
    for name, rows in games.items():
        rows.sort(key=lambda x: x.get("date", ""), reverse=True)
        latest = rows[0]
        signed_today = any(r.get("date") == today and r.get("ok") for r in rows)
        items = "".join(
            f'<div class="row"><span class="d">{r.get("date","")}</span>'
            f'<span class="a">第{r.get("day","?")}天 · {r.get("award") or "—"}</span></div>'
            for r in rows[:7])
        cards.append(f"""
<div class="card">
  <div class="game"><div class="name">{name}</div><div class="nick">{latest.get("nick","")}</div></div>
  <div class="big">{latest.get("day","?")}<span>本月已签（天）</span></div>
  <div class="award">{"今天已签到" if signed_today else "今天还没签到"} · 今日奖励 {latest.get("award") or "—"}</div>
  <div style="margin-top:8px">{items}</div>
</div>""")
    if not cards:
        cards = ['<div class="card">还没有记录</div>']
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>米游社签到</title>
<style>{CSS}</style></head><body><h1>米游社签到</h1>
<div class="sub">GitHub Actions 每天自动签到 · 更新于 {time.strftime('%m-%d %H:%M')} UTC</div>
{''.join(cards)}<div class="foot">数据来自米游社福利中心</div></body></html>"""
    with open("docs/index.html", "w") as f:
        f.write(html)


if __name__ == "__main__":
    sys.exit(main())
