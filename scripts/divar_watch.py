#!/usr/bin/env python3
"""
PishYaab / Divar watcher
=========================
هر روز آگهی‌های «پیش‌فروش» *شخصی* (نه بنگاهی/مشاوره‌املاکی) دیوار را در
محله‌های تعیین‌شده (پیش‌فرض: منطقه‌های ۵، ۲۱ و ۲۲ تهران) جست‌وجو می‌کند و
آگهی‌های تازه را از طریق یک ربات تلگرام برای کاربر ارسال می‌کند.

نکته‌ی مهم درباره‌ی تشخیص «شخصی بودن»
--------------------------------------
دیوار در فرم جست‌وجو یک فیلتر به اسم «آگهی‌دهنده: شخصی / مشاور املاک» دارد،
اما این پروژه با آزمایش مستقیم روی API عمومی دیوار متوجه شد که فرستادن این
فیلتر در بدنه‌ی درخواست جست‌وجو (`business-type`) هیچ اثری روی نتایج
دسته‌ی «presell» ندارد؛ فیلتر «شخصی» و فیلتر «مشاور املاک» دقیقاً یک نتیجه
برمی‌گردانند. پس **اعتماد به آن فیلتر اشتباه است**.

به‌جایش، نوع واقعیِ آگهی‌دهنده از خودِ صفحه‌ی جزئیات هر آگهی خوانده می‌شود:
هر آگهی یک فیلد ردیابی داخلی دارد (`webengage.business_type`) که همان
چیزی‌ست که خودِ دیوار برای هر پست ثبت می‌کند؛ مقدار `"personal"` یعنی
آگهی‌دهنده شخص حقیقی است، و مقادیری مثل `"premium-panel"` یعنی حساب
تجاری/بنگاهی (پولی) است. این پروژه دقیقاً همین فیلد را — برای هر آگهیِ تازه‌
دیده‌شده — می‌خواند و فقط `"personal"` را عبور می‌دهد. این یعنی معیار تشخیص
شخصی/بنگاهی، «نوع حساب آگهی‌دهنده» است، نه محتوای متن آگهی (پس مثلاً یک
پروژه‌ی بزرگ که توسط خودِ مالک/فرد حقیقی آگهی شده هم قبول می‌شود، و برعکس).

طراحی عمداً ساده و ارزان نگه داشته شده:
  * فقط از کتابخانه استاندارد پایتون استفاده می‌شود (بدون pip install).
  * وضعیتِ «قبلاً دیده‌شده» در یک فایل JSON کنار همین ریپو نگه داشته می‌شود
    (data/seen.json) که در گردش‌کار گیت‌هاب اکشن، بعد از هر اجرا کامیت می‌شود.
  * ارسال پیام از طریق Telegram Bot API (رایگان) انجام می‌شود.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
SEEN_PATH = ROOT / "data" / "seen.json"

DIVAR_API = "https://api.divar.ir/v8/postlist/w/search"
DIVAR_POST_API = "https://api.divar.ir/v8/posts-v2/web/{token}"
DIVAR_WEB = "https://divar.ir"
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PAGINATION_TYPE = "type.googleapis.com/post_list.PaginationData"

MAX_SEEN_TOKENS = 5000  # جلوگیری از رشد بی‌نهایت فایل وضعیت

# مقداری که دیوار برای آگهی‌دهنده‌ی «شخص حقیقی» در فیلد ردیابی
# webengage.business_type ثبت می‌کند. هر مقدار دیگری (premium-panel,
# real-estate-business, ...) یعنی حساب تجاری/بنگاهی است.
PERSONAL_BUSINESS_TYPE_VALUES = {"personal", "person", "none", ""}


# --------------------------------------------------------------------------- config


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def district_id_to_label(config: dict) -> dict[str, tuple[str, str]]:
    """نگاشت شناسه محله -> (نام منطقه, نام محله)."""
    mapping: dict[str, tuple[str, str]] = {}
    for region_name, districts in config["regions"].items():
        for district_id, district_name in districts.items():
            mapping[str(district_id)] = (region_name, district_name)
    return mapping


# --------------------------------------------------------------------------- state


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {}
    try:
        with SEEN_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict) -> None:
    if len(seen) > MAX_SEEN_TOKENS:
        ordered = sorted(seen.items(), key=lambda kv: kv[1].get("first_seen", 0))
        seen = dict(ordered[-MAX_SEEN_TOKENS:])
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SEEN_PATH.open("w", encoding="utf-8") as fh:
        json.dump(seen, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


# --------------------------------------------------------------------------- http


def _http_post_json(url: str, body: dict, timeout: float = 25.0) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json, text/plain, */*")
    req.add_header("accept-language", "fa-IR,fa;q=0.9,en;q=0.8")
    req.add_header("user-agent", USER_AGENT)
    req.add_header("origin", DIVAR_WEB)
    req.add_header("referer", DIVAR_WEB + "/")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _http_get_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("accept", "application/json, text/plain, */*")
    req.add_header("accept-language", "fa-IR,fa;q=0.9,en;q=0.8")
    req.add_header("user-agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


# --------------------------------------------------------------------------- divar search


def build_search_body(
    config: dict,
    district_ids: list[str],
    page: int,
    page_size: int,
    cursor: dict | None,
) -> dict:
    data: dict = {"category": {"str": {"value": config["category"]}}}

    if district_ids:
        data["districts"] = {"repeated_string": {"value": district_ids}}

    # توجه: فیلتر «business-type» عمداً اینجا فرستاده نمی‌شود چون آزمایش
    # مستقیم نشان داد دیوار آن را برای دسته‌ی presell نادیده می‌گیرد.
    # تشخیص شخصی/بنگاهی بعداً و به‌ازای هر آگهی، از صفحه‌ی جزئیات انجام می‌شود
    # (نگاه کنید به fetch_business_type).

    price_min = config.get("price_min")
    price_max = config.get("price_max")
    if price_min is not None or price_max is not None:
        rng = {}
        if price_min is not None:
            rng["minimum"] = int(price_min)
        if price_max is not None:
            rng["maximum"] = int(price_max)
        data["price"] = {"number_range": rng}

    body: dict = {
        "city_ids": [str(config["city_id"])],
        "search_data": {"form_data": {"data": data}},
    }

    pagination = {
        "@type": PAGINATION_TYPE,
        "page": page,
        "page_size": page_size,
    }
    if cursor:
        pagination.update(cursor)
    body["pagination_data"] = pagination
    return body


def fetch_posts(config: dict, district_ids: list[str]) -> list[dict]:
    """همه‌ی آگهی‌های صفحه‌های اول را برمی‌گرداند (خام، هنوز فیلترنشده)."""
    all_rows: list[dict] = []
    cursor = None

    for page in range(1, int(config.get("max_pages", 3)) + 1):
        body = build_search_body(config, district_ids, page, int(config.get("page_size", 60)), cursor)
        payload = _http_post_json(DIVAR_API, body)

        rows = [
            w["data"]
            for w in payload.get("list_widgets", [])
            if w.get("widget_type") == "POST_ROW"
        ]
        all_rows.extend(rows)

        pagination = payload.get("pagination") or {}
        if not pagination.get("has_next_page"):
            break
        cursor_next = pagination.get("data")
        if not cursor_next:
            break
        cursor = dict(cursor_next)
        for key in ("@type", "search_uid", "viewed_tokens"):
            cursor.pop(key, None)

        time.sleep(1.0)  # مؤدبانه با سرور دیوار رفتار کن

    return all_rows


def fetch_business_type(token: str) -> str | None:
    """نوع واقعی آگهی‌دهنده را از صفحه‌ی جزئیات آگهی می‌خواند.

    برمی‌گرداند: "personal" برای شخص حقیقی، یا مقدار دیگری (مثلاً
    "premium-panel") برای حساب تجاری/بنگاهی، یا None اگر قابل تشخیص نبود.
    """
    try:
        detail = _http_get_json(DIVAR_POST_API.format(token=token))
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] could not fetch detail for {token}: {exc}", file=sys.stderr)
        return None
    webengage = detail.get("webengage") or {}
    business_type = webengage.get("business_type")
    if business_type is None:
        return None
    return str(business_type).strip().lower()


def looks_like_agency_text(config: dict, row: dict, title: str) -> bool:
    """لایه‌ی ایمنی اضافه: اگر متن آگهی خودش را بنگاهی معرفی کند."""
    payload = (row.get("action") or {}).get("payload") or {}
    web_info = payload.get("web_info") or {}
    haystack = " ".join(
        str(x)
        for x in [
            title,
            row.get("top_description_text"),
            row.get("middle_description_text"),
            row.get("bottom_description_text"),
            web_info.get("title"),
        ]
        if x
    )
    blocklist = config.get("agency_keyword_blocklist", [])
    return any(keyword in haystack for keyword in blocklist)


def parse_row(region_lookup: dict, row: dict) -> dict | None:
    payload = (row.get("action") or {}).get("payload") or {}
    web_info = payload.get("web_info") or {}
    token = row.get("token") or payload.get("token")
    if not token:
        return None

    title = (row.get("title") or "").strip()
    district_persian = web_info.get("district_persian") or ""
    region_name = None
    for district_id, (rname, dname) in region_lookup.items():
        if dname and dname == district_persian:
            region_name = rname
            break

    return {
        "token": token,
        "row": row,
        "title": title,
        "price_text": (row.get("middle_description_text") or "").strip(),
        "district": district_persian,
        "region": region_name,
        "city": web_info.get("city_persian") or "",
        "time_text": (row.get("bottom_description_text") or "").strip(),
        "image": row.get("image_url"),
        "url": f"{DIVAR_WEB}/v/{token}",
    }


# --------------------------------------------------------------------------- telegram


def telegram_call(token: str, method: str, params: dict) -> None:
    url = TELEGRAM_API.format(token=token, method=method)
    payload = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"[error] telegram {method} failed: HTTP {exc.code} {detail}", file=sys.stderr)
        raise


def send_telegram_message(token: str, chat_id: str, text: str, photo: str | None = None) -> None:
    if photo:
        try:
            telegram_call(
                token,
                "sendPhoto",
                {
                    "chat_id": chat_id,
                    "photo": photo,
                    "caption": text[:1024],
                    "parse_mode": "HTML",
                },
            )
            return
        except Exception:
            pass  # اگر ارسال عکس شکست خورد، متن ساده بفرست
    telegram_call(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        },
    )


def format_listing_message(post: dict) -> str:
    lines = [f"🏠 <b>{escape_html(post['title'])}</b>"]
    if post.get("price_text"):
        lines.append(f"💰 {escape_html(post['price_text'])}")
    location_bits = [b for b in [post.get("region"), post.get("district")] if b]
    if location_bits:
        lines.append(f"📍 {escape_html(' - '.join(location_bits))}")
    if post.get("time_text"):
        lines.append(f"🕒 {escape_html(post['time_text'])}")
    lines.append("👤 آگهی‌دهنده: شخصی")
    lines.append(f"🔗 {post['url']}")
    return "\n".join(lines)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- main


def main() -> int:
    config = load_config()
    region_lookup = district_id_to_label(config)
    all_district_ids = list(region_lookup.keys())

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    dry_run = os.environ.get("DIVAR_DRY_RUN") == "1"

    if not dry_run and (not bot_token or not chat_id):
        print(
            "[error] TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID باید به‌عنوان "
            "secret در گیت‌هاب تنظیم شده باشند (یا DIVAR_DRY_RUN=1 برای تست).",
            file=sys.stderr,
        )
        return 1

    print(f"[info] searching {len(all_district_ids)} districts for category={config['category']}")
    raw_rows = fetch_posts(config, all_district_ids)
    print(f"[info] divar returned {len(raw_rows)} raw rows")

    seen = load_seen()
    is_first_run = len(seen) == 0
    now = int(time.time())

    # همه‌ی ردیف‌ها را پارس کن و ردیف‌های تکراری/بدون توکن را کنار بگذار
    candidates: list[dict] = []
    seen_tokens_this_run: set[str] = set()
    for row in raw_rows:
        post = parse_row(region_lookup, row)
        if post is None:
            continue
        if post["token"] in seen_tokens_this_run:
            continue
        seen_tokens_this_run.add(post["token"])
        candidates.append(post)

    new_candidates = [c for c in candidates if c["token"] not in seen]
    print(f"[info] {len(new_candidates)} candidate(s) not seen before")

    if is_first_run:
        # اولین اجراست: فقط وضعیت را با همه‌ی توکن‌های فعلی پر کن، بدون بررسی
        # نوع آگهی‌دهنده (چون پیامی هم قرار نیست ارسال شود) تا سریع و کم‌هزینه بماند.
        for post in candidates:
            seen[post["token"]] = {"first_seen": now, "title": post["title"]}
        save_seen(seen)
        print(
            f"[info] اولین اجراست؛ {len(candidates)} آگهی فعلی به عنوان «قبلاً دیده‌شده» "
            "ثبت شدند و پیامی برایشان ارسال نمی‌شود."
        )
        if not dry_run and candidates:
            send_telegram_message(
                bot_token,
                chat_id,
                (
                    "✅ ربات پیش‌یاب فعال شد.\n"
                    f"در اولین بررسی {len(candidates)} آگهی پیش‌فروش در محله‌های انتخابی "
                    "پیدا شد و به‌عنوان «قبلاً دیده‌شده» ثبت شد.\n"
                    "از این به بعد فقط آگهی‌های تازه‌ی *شخصی* (نه بنگاهی/مشاوره‌املاکی) "
                    "براتون ارسال می‌شه."
                ),
            )
        return 0

    # از این به بعد: فقط برای آگهی‌های واقعاً تازه، نوع آگهی‌دهنده را از صفحه‌ی
    # جزئیات می‌خوانیم (چون فیلتر جست‌وجوی دیوار برای این کار قابل‌اعتماد نیست).
    fresh_personal_posts: list[dict] = []
    max_checks = int(config.get("max_detail_checks_per_run", 150))

    for post in new_candidates[:max_checks]:
        business_type = fetch_business_type(post["token"])
        time.sleep(0.6)  # مؤدبانه با سرور دیوار رفتار کن

        if business_type is None:
            # اگر نتوانستیم نوع آگهی‌دهنده را تشخیص بدهیم، این‌بار رد می‌شویم
            # ولی توکن را «دیده‌شده» ثبت نمی‌کنیم تا فردا دوباره امتحان شود.
            continue

        is_personal = business_type in PERSONAL_BUSINESS_TYPE_VALUES
        seen[post["token"]] = {
            "first_seen": now,
            "title": post["title"],
            "business_type": business_type,
        }

        if not is_personal:
            continue
        if looks_like_agency_text(config, post["row"], post["title"]):
            continue

        fresh_personal_posts.append(post)

    save_seen(seen)
    print(f"[info] {len(fresh_personal_posts)} new PERSONAL listing(s) found")

    max_notify = int(config.get("max_notifications_per_run", 40))
    to_send = fresh_personal_posts[:max_notify]
    overflow = len(fresh_personal_posts) - len(to_send)

    if dry_run:
        for post in to_send:
            print("----")
            print(format_listing_message(post))
        if overflow > 0:
            print(f"... and {overflow} more")
        return 0

    for post in to_send:
        try:
            send_telegram_message(bot_token, chat_id, format_listing_message(post), post.get("image"))
        except Exception as exc:  # noqa: BLE001 - یک پیام ناموفق نباید بقیه را متوقف کند
            print(f"[error] failed to send message for {post['token']}: {exc}", file=sys.stderr)
        time.sleep(1.2)  # رعایت محدودیت نرخ تلگرام

    if overflow > 0:
        send_telegram_message(
            bot_token,
            chat_id,
            f"➕ {overflow} آگهی جدید دیگر هم پیدا شد که برای جلوگیری از اسپم ارسال نشدند.",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
