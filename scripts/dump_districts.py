#!/usr/bin/env python3
"""Diagnostic: inspect raw POST_ROW fields to find a reliable business-type
signal, and check whether the business-type=personal filter is actually
enforced server-side."""
import json
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


DISTRICTS = ["78", "82", "167", "172"]  # شهرک غرب، پونک، اکباتان، صادقیه

body_personal = {
    "city_ids": ["1"],
    "search_data": {
        "form_data": {
            "data": {
                "category": {"str": {"value": "presell"}},
                "districts": {"repeated_string": {"value": DISTRICTS}},
                "business-type": {"str": {"value": "personal"}},
            }
        }
    },
    "pagination_data": {
        "@type": "type.googleapis.com/post_list.PaginationData",
        "page": 1,
        "page_size": 24,
    },
}

body_agency = {
    "city_ids": ["1"],
    "search_data": {
        "form_data": {
            "data": {
                "category": {"str": {"value": "presell"}},
                "districts": {"repeated_string": {"value": DISTRICTS}},
                "business-type": {"str": {"value": "real-estate-business"}},
            }
        }
    },
    "pagination_data": {
        "@type": "type.googleapis.com/post_list.PaginationData",
        "page": 1,
        "page_size": 24,
    },
}

for label, body in [("PERSONAL FILTER", body_personal), ("AGENCY FILTER", body_agency)]:
    print("=" * 20, label, "=" * 20)
    payload = post_json("https://api.divar.ir/v8/postlist/w/search", body)
    rows = [w["data"] for w in payload.get("list_widgets", []) if w.get("widget_type") == "POST_ROW"]
    print(f"row count: {len(rows)}")
    if rows:
        # print full first row raw json to inspect available fields
        print("---- FULL FIRST ROW ----")
        print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:4000])
    for r in rows[:12]:
        payload_ = (r.get("action") or {}).get("payload") or {}
        web_info = payload_.get("web_info") or {}
        print("-", r.get("title"), "|", web_info.get("district_persian"), "|",
              r.get("top_description_text"), "|", r.get("middle_description_text"))

    # cross-check with post detail webengage.business_type for first 5 rows
    print("---- webengage.business_type for first 5 ----")
    for r in rows[:5]:
        payload_ = (r.get("action") or {}).get("payload") or {}
        token = r.get("token") or payload_.get("token")
        if not token:
            continue
        try:
            detail = get_json(f"https://api.divar.ir/v8/posts-v2/web/{token}")
            we = detail.get("webengage") or {}
            print(token, "->", we.get("business_type"), "|", r.get("title"))
        except Exception as exc:
            print(token, "-> error", exc)
