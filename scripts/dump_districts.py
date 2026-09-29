#!/usr/bin/env python3
"""Validate each candidate district id against Divar's real API (one at a time)."""
import json
import time
import urllib.error
import urllib.request

CANDIDATES = {
    "78": "شهرک غرب", "82": "پونک", "145": "جنت‌آباد شمالی", "146": "جنت‌آباد مرکزی",
    "148": "جنت‌آباد جنوبی", "147": "شاهین", "158": "سازمان برنامه شمالی",
    "167": "اکباتان", "172": "صادقیه", "171": "طرشت", "139": "مرزداران", "88": "گیشا",
    "195": "استاد معین", "178": "تهرانسر شرقی", "175": "شهرک استقلال", "170": "فردوس",
    "173": "اباذر", "169": "شهرک آپادانا", "168": "کوی بیمه", "355": "آریاشهر",
    "155": "شهر زیبا",
    "151": "شهران شمالی", "152": "شهران جنوبی", "164": "شهرک آزادی", "374": "وردآورد",
    "154": "بهاران",
    "311": "شهرک چیتگر", "306": "چیتگر جنوبی", "188": "دریاچه شهدای خلیج فارس",
    "161": "دهکده المپیک", "162": "زیبادشت", "165": "گلستان (شهرک راه‌آهن)",
    "163": "شهرک صدرا",
}

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


valid = {}
invalid = {}

for did, name in CANDIDATES.items():
    body = {
        "city_ids": ["1"],
        "search_data": {
            "form_data": {
                "data": {
                    "category": {"str": {"value": "presell"}},
                    "districts": {"repeated_string": {"value": [did]}},
                }
            }
        },
        "pagination_data": {
            "@type": "type.googleapis.com/post_list.PaginationData",
            "page": 1,
            "page_size": 1,
        },
    }
    try:
        post_json("https://api.divar.ir/v8/postlist/w/search", body)
        valid[did] = name
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        invalid[did] = {"name": name, "status": exc.code, "detail": detail[:200]}
    except Exception as exc:
        invalid[did] = {"name": name, "error": str(exc)}
    time.sleep(0.7)

print("VALID:")
print(json.dumps(valid, ensure_ascii=False, indent=2))
print("INVALID:")
print(json.dumps(invalid, ensure_ascii=False, indent=2))
