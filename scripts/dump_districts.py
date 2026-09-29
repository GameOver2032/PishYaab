#!/usr/bin/env python3
"""Temporary diagnostic: dump Divar's real district filter options for Tehran."""
import json
import urllib.request

BODY = {
    "city_ids": ["1"],
    "search_data": {"form_data": {"data": {"category": {"str": {"value": "presell"}}}}},
}

req = urllib.request.Request(
    "https://api.divar.ir/v8/postlist/w/filters",
    data=json.dumps(BODY).encode("utf-8"),
    method="POST",
)
req.add_header("content-type", "application/json")
req.add_header("accept", "application/json")
req.add_header("origin", "https://divar.ir")
req.add_header("referer", "https://divar.ir/")
req.add_header(
    "user-agent",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)

with urllib.request.urlopen(req, timeout=25) as resp:
    data = json.loads(resp.read().decode("utf-8", "replace"))

print(json.dumps(data, ensure_ascii=False, indent=2)[:20000])
