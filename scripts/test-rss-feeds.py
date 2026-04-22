#!/usr/bin/env python3
"""
Test RSS feeds to diagnose why no new articles are being saved.
Checks published dates and content hashes for the top 10 entries per feed.
"""

import feedparser
import hashlib
import requests
from datetime import datetime

FEEDS = [
    ("Wall Street Journal", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("Financial Times", "https://www.ft.com/markets?format=rss"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://www.marketwatch.com/rss/topstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Benzinga", "https://www.benzinga.com/feed"),
    ("Motley Fool", "https://www.fool.com/feeds/index.aspx"),
    ("Insider Monkey", "https://www.insidermonkey.com/blog/feed/"),
    ("The Economist", "https://www.economist.com/finance-and-economics/rss.xml"),
    ("Fortune", "https://fortune.com/feed/"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Crypto News", "https://cryptonews.com/news/feed/"),
    ("U.S. News Money", "https://www.usnews.com/rss/news"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TODAY = datetime.now().date()


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


def run():
    total_new = 0
    total_stale = 0

    for name, url in FEEDS:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"  {url}")
        print(f"{'='*60}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=(5, 10))
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            entries = feed.entries[:10]
            print(f"  feed entries: {len(feed.entries)} total, showing top {len(entries)}")

            feed_new = 0
            feed_stale = 0
            for e in entries:
                title = e.get("title", "(no title)")
                link = e.get("link", "")
                summary = e.get("summary", e.get("description", ""))

                if hasattr(e, "published_parsed") and e.published_parsed:
                    pub = datetime(*e.published_parsed[:6])
                    pub_str = pub.strftime("%Y-%m-%d %H:%M")
                    age_days = (TODAY - pub.date()).days
                    age_label = f"{age_days}d ago" if age_days > 0 else "TODAY"
                else:
                    pub_str = "unknown"
                    age_label = "?"

                h = content_hash(summary)
                url_h = content_hash(link)

                is_new = age_days == 0 if pub_str != "unknown" else None
                marker = "NEW " if is_new else "OLD "
                if is_new:
                    feed_new += 1
                else:
                    feed_stale += 1

                print(f"  {marker} {pub_str} ({age_label}) | sum_hash={h} url_hash={url_h} | {title[:60]}")

            print(f"  --> new today: {feed_new}, stale: {feed_stale}")
            total_new += feed_new
            total_stale += feed_stale

        except Exception as ex:
            print(f"  ERROR: {ex}")

    print(f"\n{'='*60}")
    print(f"SUMMARY: {total_new} new articles today, {total_stale} stale across all feeds")
    print(f"{'='*60}")


if __name__ == "__main__":
    run()
