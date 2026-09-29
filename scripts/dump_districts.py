#!/usr/bin/env python3
import json
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_json(url):
    req = urllib.request.Request(url, method="GET")
    req.add_header("accept", "application/json")
    req.add_header("user-agent", UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


detail = get_json("https://api.divar.ir/v8/posts-v2/web/ga76ItBU")
text = json.dumps(detail, ensure_ascii=False)
print("LEN", len(text))

# print webengage + seo + analytics fully, they're usually small
for key in ("webengage", "seo", "analytics", "city", "share"):
    print("=====", key, "=====")
    print(json.dumps(detail.get(key), ensure_ascii=False, indent=2)[:3000])
