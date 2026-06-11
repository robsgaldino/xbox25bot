#!/usr/bin/env python3
"""
Notícias americanas sobre o Xbox 25th Anniversary / Series X25 via Google News RSS.

Usado pelo GitHub Actions (publica docs/news.json para o dashboard da nuvem)
e pelo dashboard.py local (endpoint /api/news com cache).
"""

import json
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "docs" / "news.json"

QUERIES = [
    '"xbox 25th anniversary"',
    '"xbox series x25" OR "series x25"',
    '"series x 25th" OR "xbox series x 25th anniversary"',
    '"xbox sx 25th" OR "sx 25th"',
    'xbox "25th anniversary" console (preorder OR "pre-order" OR "limited edition")',
]
UA = "Mozilla/5.0 (compatible; xbox25bot/1.0)"
MAX_ITEMS = 30


def fetch_query(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=en-US&gl=US&ceid=US:en")
    # curl do sistema: usa a cadeia de certificados do macOS, como no xbox25bot
    proc = subprocess.run(["curl", "-sS", "-L", "--compressed", "--max-time", "20",
                           "-A", UA, "--fail-with-body", url],
                          capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"curl rc={proc.returncode}: {proc.stderr.decode(errors='ignore')[:200]}")
    root = ET.fromstring(proc.stdout)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        source = (it.findtext("source") or "").strip()
        try:
            ts = int(parsedate_to_datetime(it.findtext("pubDate")).timestamp())
        except (TypeError, ValueError):
            ts = 0
        if title and link:
            items.append({"title": title, "url": link, "source": source, "ts": ts})
    return items


def collect():
    seen, out = set(), []
    for q in QUERIES:
        try:
            items = fetch_query(q)
        except Exception:
            continue
        for n in items:
            key = n["title"].lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            out.append(n)
    out.sort(key=lambda n: -n["ts"])
    return out[:MAX_ITEMS]


if __name__ == "__main__":
    news = collect()
    OUT.write_text(json.dumps({"updated": int(time.time()), "items": news},
                              ensure_ascii=False, indent=1))
    print(f"{len(news)} notícias salvas em {OUT}")
