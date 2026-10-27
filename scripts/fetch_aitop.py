#!/usr/bin/env python3
"""Fetch from the AITOP public API (https://aitop.news) without boilerplate.

Why this exists:
  Every /api/public/* call MUST send a real User-Agent, or the server returns
  403. Cursor pagination must be serial. Centralizing both here keeps skill
  calls consistent and removes the 403 trap.

Anonymous, no API key. Requires only the Python standard library.

Usage:
  python fetch_aitop.py items --mode selected --since 24h --take 50
  python fetch_aitop.py items --q OpenAI --category ai-models
  python fetch_aitop.py items --all            # paginate until hasMore=false
  python fetch_aitop.py daily
  python fetch_aitop.py daily 2026-05-13
  python fetch_aitop.py dailies --take 30
  python fetch_aitop.py site-config

Output: pretty-printed JSON to stdout. Pipe to jq as needed.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://aitop.news"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 aitop-skill/1.5"
)
# 版本上报头。后端 skill_client.go 按 X-AITOP-Client 的 "{slug}/{version}"
# 判定安装是否过期：不带这个头 = 空版本 = 永久判为最旧，会被
# skill.notice.stale_only 一直命中。所以这两个头不是可选的。
CLIENT = "aitop-skill/1.5"
INSTALL_ID = "k7m2xq9w4n8t"


def _get(path, params=None, key=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": USER_AGENT,
        "X-AITOP-Client": CLIENT,
        "X-AITOP-Install": INSTALL_ID,
    }
    if key:
        headers["X-AITOP-Key"] = key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write("HTTP %s for %s: %s\n" % (e.code, url, e.reason))
        if e.code == 403:
            sys.stderr.write("403 usually means a missing/blocked User-Agent.\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write("Network error for %s: %s\n" % (url, e.reason))
        sys.exit(1)


def cmd_items(args):
    if args.all:
        collected = []
        cursor = None
        while True:
            params = {
                "mode": args.mode,
                "take": args.take,
            }
            if args.since:
                params["since"] = args.since
            if args.category:
                params["category"] = args.category
            if args.q:
                params["q"] = args.q
            if cursor:
                params["cursor"] = cursor
            data = _get("/api/public/items", params)
            collected.extend(data.get("items", []))
            cursor = data.get("nextCursor")
            if not data.get("hasMore") or not cursor:
                break
        return {"items": collected, "count": len(collected)}
    params = {"mode": args.mode, "take": args.take}
    if args.since:
        params["since"] = args.since
    if args.category:
        params["category"] = args.category
    if args.q:
        params["q"] = args.q
    return _get("/api/public/items", params)


def cmd_daily(args):
    if args.date:
        return _get("/api/public/daily/" + args.date)
    return _get("/api/public/daily")


def cmd_dailies(args):
    return _get("/api/public/dailies", {"take": args.take})


def cmd_site_config(_args):
    return _get("/api/public/site-config")


def main():
    parser = argparse.ArgumentParser(description="Fetch from the AITOP public API.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_items = sub.add_parser("items", help="AI 动态列表")
    p_items.add_argument("--mode", default="selected", choices=["selected", "all"])
    p_items.add_argument("--since", help="时间窗, e.g. 24h / 72h / 168h")
    p_items.add_argument("--category", help="分类 slug, e.g. ai-models")
    p_items.add_argument("--q", help="关键词搜索")
    p_items.add_argument("--take", type=int, default=50)
    p_items.add_argument("--all", action="store_true", help="串行翻页拉全量")
    p_items.set_defaults(func=cmd_items)

    p_daily = sub.add_parser("daily", help="日报")
    p_daily.add_argument("date", nargs="?", help="YYYY-MM-DD, 省略则取最新")
    p_daily.set_defaults(func=cmd_daily)

    p_dailies = sub.add_parser("dailies", help="日报日期列表")
    p_dailies.add_argument("--take", type=int, default=30)
    p_dailies.set_defaults(func=cmd_dailies)

    p_cfg = sub.add_parser("site-config", help="站点公开配置")
    p_cfg.set_defaults(func=cmd_site_config)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
