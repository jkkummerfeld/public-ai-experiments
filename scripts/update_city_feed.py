#!/usr/bin/env python3
"""
Check theflightdeal.com for posts that mention a flight to/from a given
city, and add any new ones to a local RSS feed file that can be subscribed
to directly in an RSS reader (e.g. Feedly).

Meant to run on a schedule (see .github/workflows/*-deal-feed.yml), which
commits the updated feed file back to the repo whenever new matches are
found. The output feed accumulates matches over time (deduped by link),
capped by --max-items / --max-age-days so it doesn't grow forever.

Usage:
    python3 scripts/update_city_feed.py --city Sydney [--output feed/sydney-deals.xml]
                                         [--max-items 100] [--max-age-days 180]
                                         [--dry-run]
"""
import argparse
import sys
import urllib.request
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime

SOURCE_FEED_URL = "https://www.theflightdeal.com/feed/"
FEED_LINK = "https://www.theflightdeal.com/"
# The site returns 403 to requests without a browser-like User-Agent.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_source_feed(url=SOURCE_FEED_URL):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _parse_items(root):
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        categories = [(c.text or "").strip() for c in item.findall("category")]
        pub_date_raw = item.findtext("pubDate")
        pub_date = parsedate_to_datetime(pub_date_raw) if pub_date_raw else None
        if pub_date is not None and pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        items.append(
            {
                "title": title,
                "link": link,
                "description": description,
                "categories": categories,
                "pub_date": pub_date,
            }
        )
    return items


def parse_source_items(feed_bytes):
    return _parse_items(ET.fromstring(feed_bytes))


def parse_existing_output(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return []
    return _parse_items(ET.fromstring(data))


def mentions_city(item, city):
    haystacks = [item["title"], item["description"]] + item["categories"]
    return any(city.lower() in (text or "").lower() for text in haystacks)


def merge_items(existing, new_matches, max_items, max_age_days):
    by_link = {item["link"]: item for item in existing if item["link"]}
    for item in new_matches:
        if item["link"]:
            by_link[item["link"]] = item

    merged = list(by_link.values())
    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        merged = [
            item for item in merged if item["pub_date"] is None or item["pub_date"] >= cutoff
        ]

    epoch = datetime.min.replace(tzinfo=timezone.utc)
    merged.sort(key=lambda item: item["pub_date"] or epoch, reverse=True)
    return merged[:max_items]


def _cdata(text):
    return text.replace("]]>", "]]]]><![CDATA[>")


def render_feed(items, title, description):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{saxutils.escape(title)}</title>",
        f"<link>{saxutils.escape(FEED_LINK)}</link>",
        f"<description>{saxutils.escape(description)}</description>",
        f"<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>",
    ]
    for item in items:
        lines.append("<item>")
        lines.append(f"<title>{saxutils.escape(item['title'])}</title>")
        lines.append(f"<link>{saxutils.escape(item['link'])}</link>")
        lines.append(f'<guid isPermaLink="true">{saxutils.escape(item["link"])}</guid>')
        if item["pub_date"] is not None:
            lines.append(f"<pubDate>{format_datetime(item['pub_date'])}</pubDate>")
        if item["description"]:
            lines.append(f"<description><![CDATA[{_cdata(item['description'])}]]></description>")
        lines.append("</item>")
    lines.append("</channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--city", required=True, help="City to match against (e.g. Sydney, Berlin)"
    )
    parser.add_argument("--output", required=True, help="Path to the output feed file")
    parser.add_argument(
        "--max-items", type=int, default=100, help="Cap on entries kept in the output feed"
    )
    parser.add_argument(
        "--max-age-days", type=int, default=180, help="Drop entries older than this many days"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print new matches instead of writing the output feed file",
    )
    args = parser.parse_args()

    feed_title = f"The Flight Deal: {args.city}"
    feed_description = (
        f"Posts from theflightdeal.com that mention a flight to/from {args.city}, "
        "checked every 6 hours."
    )

    source_items = parse_source_items(fetch_source_feed())
    matches = [item for item in source_items if mentions_city(item, args.city)]

    existing = parse_existing_output(args.output)
    existing_links = {item["link"] for item in existing}
    new_matches = [item for item in matches if item["link"] not in existing_links]

    if not new_matches:
        print(f"No new {args.city} flight deals found.")
        return 0

    print(f"Found {len(new_matches)} new {args.city} flight deal(s):")
    for item in new_matches:
        print(f"- {item['title']}\n  {item['link']}")

    if args.dry_run:
        return 0

    merged = merge_items(existing, new_matches, args.max_items, args.max_age_days)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(render_feed(merged, feed_title, feed_description))
    print(f"Wrote {len(merged)} entries to {args.output}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
