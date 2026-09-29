#!/usr/bin/env python3
import json
import re
import urllib.request

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
        "search_data": {"query": query, "form_data": {"data": {}}},
        "pagination_data": {
            "@type": "type.googleapis.com/post_list.PaginationData",
            "page": 1,
            "page_size": 24,
        },
    }
    payload = post_json("https://api.divar.ir/v8/postlist/w/search", body)
    return [
        w["data"] for w in payload.get("list_widgets", []) if w.get("widget_type") == "POST_ROW"
    ]


rows = search("آریاشهر")
found = None
for row in rows:
    payload = (row.get("action") or {}).get("payload") or {}
    web_info = payload.get("web_info") or {}
    district = web_info.get("district_persian") or ""
    if "آریاشهر" in district:
        token = row.get("token") or payload.get("token")
        detail = get_json(f"https://api.divar.ir/v8/posts-v2/web/{token}")
        crumbs = ((detail.get("seo") or {}).get("bread_crumb")) or []
        for c in crumbs:
            ids = (
                ((c.get("search_data") or {}).get("form_data") or {})
                .get("data", {})
                .get("districts", {})
                .get("repeated_string", {})
                .get("value")
            )
            if ids:
                found = {"district": district, "token": token, "ids": ids, "crumb_name": c.get("name")}
        break

print(json.dumps(found, ensure_ascii=False, indent=2))
print("---all rows districts seen---")
seen_districts = sorted({((r.get("action") or {}).get("payload") or {}).get("web_info", {}).get("district_persian") for r in rows})
print(json.dumps(seen_districts, ensure_ascii=False))
