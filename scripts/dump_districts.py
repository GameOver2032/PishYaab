#!/usr/bin/env python3
"""Temporary diagnostic: resolve real Divar district_ids for our target
neighborhoods by searching for each name, then reading district_id off a
matching post's detail endpoint."""
import json
import time
import urllib.request

NEIGHBORHOODS = [
    "شهرک غرب", "پونک", "جنت آباد شمالی", "جنت آباد مرکزی", "جنت آباد جنوبی",
    "شاهین", "سازمان برنامه", "اکباتان", "صادقیه", "طرشت", "مرزداران", "گیشا",
    "استاد معین", "تهرانسر", "شهرک استقلال", "فردوس", "اباذر", "شهرک آپادانا",
    "کوی بیمه", "آریاشهر", "شهر زیبا",
    "شهران شمالی", "شهران جنوبی", "شهرک آزادی", "وردآورد", "باغ فیض", "آزادگان",
    "شهرک چیتگر", "چیتگر جنوبی", "دریاچه شهدای خلیج فارس", "دهکده المپیک",
    "زیبادشت", "شهرک راه آهن", "شهرک صدرا", "شهرک گلستان",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json")
    req.add_header("origin", "https://divar.ir")
    req.add_header("referer", "https://divar.ir/")
    req.add_header("user-agent", UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def get_json(url):
    req = urllib.request.Request(url, method="GET")
    req.add_header("accept", "application/json")
    req.add_header("user-agent", UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def search(query):
    body = {
        "city_ids": ["1"],
        "search_data": {
            "query": query,
            "form_data": {"data": {}},
        },
        "pagination_data": {
            "@type": "type.googleapis.com/post_list.PaginationData",
            "page": 1,
            "page_size": 24,
        },
    }
    payload = post_json("https://api.divar.ir/v8/postlist/w/search", body)
    rows = [
        w["data"]
        for w in payload.get("list_widgets", [])
        if w.get("widget_type") == "POST_ROW"
    ]
    return rows


results = {}
for name in NEIGHBORHOODS:
    try:
        rows = search(name)
    except Exception as exc:
        results[name] = {"error": f"search failed: {exc}"}
        continue

    found = False
    for row in rows:
        payload = (row.get("action") or {}).get("payload") or {}
        web_info = payload.get("web_info") or {}
        district = web_info.get("district_persian") or ""
        if name.replace(" ", "") not in district.replace(" ", "") and district.replace(" ", "") not in name.replace(" ", ""):
            continue
        token = row.get("token") or payload.get("token")
        if not token:
            continue
        try:
            detail = get_json(f"https://api.divar.ir/v8/posts-v2/web/{token}")
        except Exception as exc:
            results[name] = {"error": f"detail failed: {exc}"}
            found = True
            break
        district_id = None
        # try a few plausible locations for the id
        for key in ("district_id",):
            if key in detail:
                district_id = detail[key]
        if district_id is None:
            loc = detail.get("webengage") or {}
            district_id = loc.get("district_id")
        results[name] = {
            "district_persian": district,
            "token": token,
            "district_id": district_id,
            "raw_keys": list(detail.keys()),
        }
        found = True
        break
    if not found:
        results[name] = {"error": "no matching row found", "row_count": len(rows)}
    time.sleep(0.9)

print(json.dumps(results, ensure_ascii=False, indent=2))
