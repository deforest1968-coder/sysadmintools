#!/usr/bin/env python3
"""
IT Security Feed Aggregator
Pulls latest exploits, patches, zero-days, and malware info from major sources
and renders a local HTML webpage.
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import html
import datetime
import webbrowser
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Feed sources ──────────────────────────────────────────────────────────────

FEEDS = [
    # CVE / Vulnerability databases
    {"name": "NVD Recent CVEs",         "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml",        "tag": "CVE"},
    {"name": "CVE Mitre",               "url": "https://cve.mitre.org/data/downloads/allitems-cvrf.xml",               "tag": "CVE"},  # fallback

    # Threat intelligence
    {"name": "US-CERT Alerts",          "url": "https://www.cisa.gov/uscert/ncas/alerts.xml",                         "tag": "ALERT"},
    {"name": "CISA Advisories",         "url": "https://www.cisa.gov/uscert/ncas/advisories.xml",                     "tag": "ADVISORY"},
    {"name": "CISA ICS Advisories",     "url": "https://www.cisa.gov/uscert/ics/advisories.xml",                      "tag": "ICS"},

    # Exploit databases
    {"name": "Exploit-DB",              "url": "https://www.exploit-db.com/rss.xml",                                  "tag": "EXPLOIT"},
    {"name": "Packet Storm",            "url": "https://rss.packetstormsecurity.com/files/",                          "tag": "EXPLOIT"},

    # Malware / threat research
    {"name": "Malwarebytes Labs",       "url": "https://www.malwarebytes.com/blog/feed",                              "tag": "MALWARE"},
    {"name": "Securelist (Kaspersky)",  "url": "https://securelist.com/feed/",                                        "tag": "MALWARE"},
    {"name": "Malware Traffic Analysis","url": "https://www.malware-traffic-analysis.net/blog-entries.rss",           "tag": "MALWARE"},

    # Vendor security bulletins
    {"name": "Microsoft MSRC",          "url": "https://api.msrc.microsoft.com/update-guide/rss",                     "tag": "PATCH"},
    {"name": "Google Project Zero",     "url": "https://googleprojectzero.blogspot.com/feeds/posts/default",          "tag": "ZERO-DAY"},
    {"name": "Mozilla Security",        "url": "https://blog.mozilla.org/security/feed/",                             "tag": "PATCH"},
    {"name": "RedHat Security",         "url": "https://www.redhat.com/en/rss/blog/channel/security",                 "tag": "PATCH"},

    # Security news
    {"name": "The Hacker News",         "url": "https://feeds.feedburner.com/TheHackersNews",                         "tag": "NEWS"},
    {"name": "Krebs on Security",       "url": "https://krebsonsecurity.com/feed/",                                   "tag": "NEWS"},
    {"name": "Bleeping Computer",       "url": "https://www.bleepingcomputer.com/feed/",                              "tag": "NEWS"},
    {"name": "Dark Reading",            "url": "https://www.darkreading.com/rss.xml",                                 "tag": "NEWS"},
    {"name": "SecurityWeek",            "url": "https://feeds.feedburner.com/Securityweek",                           "tag": "NEWS"},
    {"name": "Graham Cluley",           "url": "https://grahamcluley.com/feed/",                                      "tag": "NEWS"},
    {"name": "Schneier on Security",    "url": "https://www.schneier.com/feed/atom/",                                 "tag": "NEWS"},
    {"name": "Troy Hunt Blog",          "url": "https://www.troyhunt.com/rss/",                                       "tag": "NEWS"},

    # Threat intel / IOC
    {"name": "AlienVault OTX",         "url": "https://otx.alienvault.com/api/v1/pulses/subscribed_by_author?author_name=AlienVault&limit=20&page=1", "tag": "THREAT", "json": True},
    {"name": "SANS ISC",               "url": "https://isc.sans.edu/rssfeed_full.xml",                               "tag": "THREAT"},
    {"name": "ThreatPost",             "url": "https://threatpost.com/feed/",                                         "tag": "THREAT"},
]

TAG_COLORS = {
    "CVE":      "#e74c3c",
    "EXPLOIT":  "#c0392b",
    "ZERO-DAY": "#8e44ad",
    "MALWARE":  "#e67e22",
    "ALERT":    "#e74c3c",
    "ADVISORY": "#d35400",
    "ICS":      "#f39c12",
    "PATCH":    "#27ae60",
    "THREAT":   "#2980b9",
    "NEWS":     "#7f8c8d",
}

# ── Fetch helpers ─────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "SecurityFeedBot/1.0 (research aggregator)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
}

def fetch_url(url, timeout=12):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def parse_rss(data):
    """Parse RSS/Atom feed, return list of dicts."""
    items = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Atom feed
    if root.tag in ("{http://www.w3.org/2005/Atom}feed", "feed"):
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link = (link_el.get("href") if link_el is not None else "") or ""
            summary = (entry.findtext("atom:summary", namespaces=ns) or
                       entry.findtext("atom:content", namespaces=ns) or "").strip()
            pub = (entry.findtext("atom:published", namespaces=ns) or
                   entry.findtext("atom:updated", namespaces=ns) or "").strip()
            items.append({"title": title, "link": link, "summary": summary, "pub": pub})
        return items

    # RSS 2.0 / RDF
    for item in root.iter("item"):
        title   = (item.findtext("title") or "").strip()
        link    = (item.findtext("link") or "").strip()
        summary = (item.findtext("description") or item.findtext("summary") or "").strip()
        pub     = (item.findtext("pubDate") or item.findtext("date") or "").strip()
        items.append({"title": title, "link": link, "summary": summary, "pub": pub})
    return items

def fetch_feed(feed):
    results = []
    try:
        raw = fetch_url(feed["url"])
        if feed.get("json"):
            # AlienVault OTX JSON endpoint
            data = json.loads(raw)
            for pulse in data.get("results", [])[:15]:
                results.append({
                    "source": feed["name"],
                    "tag":    feed["tag"],
                    "title":  pulse.get("name", ""),
                    "link":   f"https://otx.alienvault.com/pulse/{pulse.get('id','')}",
                    "summary": pulse.get("description", ""),
                    "pub":    pulse.get("created", ""),
                })
        else:
            items = parse_rss(raw)
            for item in items[:20]:
                item.update({"source": feed["name"], "tag": feed["tag"]})
                results.append(item)
    except Exception as e:
        results.append({
            "source":  feed["name"],
            "tag":     feed["tag"],
            "title":   f"[Could not fetch: {e}]",
            "link":    feed["url"],
            "summary": "",
            "pub":     "",
            "error":   True,
        })
    return results

# ── HTML renderer ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IT Security Feed — {timestamp}</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 32px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 100; }}
  header h1 {{ font-size: 1.3rem; color: #fff; }}
  header .meta {{ color: var(--muted); font-size: 12px; }}
  .controls {{ margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }}
  .filter-btn {{ background: var(--bg); border: 1px solid var(--border); color: var(--muted); padding: 4px 12px; border-radius: 20px; cursor: pointer; font-size: 12px; transition: all .15s; }}
  .filter-btn:hover, .filter-btn.active {{ color: #fff; border-color: var(--accent); background: #1f3045; }}
  .filter-btn[data-tag="CVE"].active      {{ border-color:#e74c3c; background:#2d1215; color:#e74c3c; }}
  .filter-btn[data-tag="EXPLOIT"].active  {{ border-color:#c0392b; background:#2d1215; color:#c0392b; }}
  .filter-btn[data-tag="ZERO-DAY"].active {{ border-color:#8e44ad; background:#1e1228; color:#8e44ad; }}
  .filter-btn[data-tag="MALWARE"].active  {{ border-color:#e67e22; background:#2d1a0a; color:#e67e22; }}
  .filter-btn[data-tag="PATCH"].active    {{ border-color:#27ae60; background:#0d2318; color:#27ae60; }}
  .filter-btn[data-tag="THREAT"].active   {{ border-color:#2980b9; background:#0d1e2d; color:#2980b9; }}
  .filter-btn[data-tag="NEWS"].active     {{ border-color:#7f8c8d; background:#1a1e1f; color:#aaa; }}
  .filter-btn[data-tag="ALERT"].active    {{ border-color:#e74c3c; background:#2d1215; color:#e74c3c; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px; }}
  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
  .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px 16px; font-size: 13px; }}
  .stat strong {{ color: #fff; font-size: 1.4rem; display: block; }}
  .grid {{ display: grid; gap: 12px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; transition: border-color .15s; }}
  .card:hover {{ border-color: var(--accent); }}
  .card.error {{ opacity: 0.45; }}
  .card-top {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 6px; }}
  .tag {{ font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 12px; color: #fff; white-space: nowrap; flex-shrink: 0; margin-top: 3px; }}
  .card-title a {{ color: #fff; text-decoration: none; font-weight: 600; font-size: 14px; line-height: 1.4; }}
  .card-title a:hover {{ color: var(--accent); }}
  .card-meta {{ font-size: 11px; color: var(--muted); margin-bottom: 4px; }}
  .card-meta .source {{ color: var(--accent); }}
  .summary {{ font-size: 12px; color: var(--muted); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
  .hidden {{ display: none; }}
  footer {{ text-align: center; color: var(--muted); font-size: 11px; padding: 32px; }}
  #search {{ background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 5px 12px; border-radius: 6px; font-size: 13px; width: 200px; }}
  #search:focus {{ outline: none; border-color: var(--accent); }}
</style>
</head>
<body>
<header>
  <div>
    <h1>🛡 IT Security Feed</h1>
    <div class="meta">Generated {timestamp} · {total} items from {sources} sources</div>
  </div>
  <div class="controls">
    <input id="search" type="text" placeholder="Search…" oninput="applyFilters()">
    <button class="filter-btn active" data-tag="ALL" onclick="setTag('ALL')">All</button>
    {filter_buttons}
  </div>
</header>
<main>
  <div class="stats">{stat_cards}</div>
  <div class="grid" id="feed">
    {cards}
  </div>
</main>
<footer>Security Feed Aggregator · {timestamp} · For research and awareness only</footer>
<script>
let activeTag = 'ALL';
function setTag(tag) {{
  activeTag = tag;
  document.querySelectorAll('.filter-btn').forEach(b => {{
    b.classList.toggle('active', b.dataset.tag === tag);
  }});
  applyFilters();
}}
function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.card').forEach(card => {{
    const tagMatch = activeTag === 'ALL' || card.dataset.tag === activeTag;
    const textMatch = !q || card.textContent.toLowerCase().includes(q);
    card.classList.toggle('hidden', !(tagMatch && textMatch));
  }});
}}
</script>
</body>
</html>"""

def tag_badge(tag):
    color = TAG_COLORS.get(tag, "#555")
    return f'<span class="tag" style="background:{color}">{html.escape(tag)}</span>'

def clean_summary(text):
    """Strip HTML tags from summary for display."""
    import re
    text = re.sub(r'<[^>]+>', '', text or '')
    text = html.unescape(text)
    return text[:300].strip()

def render_html(all_items):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Count by tag
    tag_counts = {}
    sources_seen = set()
    for item in all_items:
        if not item.get("error"):
            tag_counts[item["tag"]] = tag_counts.get(item["tag"], 0) + 1
            sources_seen.add(item["source"])

    # Filter buttons
    filter_buttons = ""
    for tag in sorted(tag_counts):
        filter_buttons += f'<button class="filter-btn" data-tag="{tag}" onclick="setTag(\'{tag}\')">{tag} <small>({tag_counts[tag]})</small></button>\n'

    # Stat cards
    stat_cards = f'<div class="stat"><strong>{len([i for i in all_items if not i.get("error")])}</strong>Items</div>'
    stat_cards += f'<div class="stat"><strong>{len(sources_seen)}</strong>Sources</div>'
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        color = TAG_COLORS.get(tag, "#555")
        stat_cards += f'<div class="stat"><strong style="color:{color}">{count}</strong>{tag}</div>'

    # Cards
    cards_html = ""
    for item in all_items:
        error_class = " error" if item.get("error") else ""
        title = html.escape(item.get("title") or "(no title)")
        link  = html.escape(item.get("link") or "#")
        source = html.escape(item.get("source") or "")
        pub   = html.escape(item.get("pub") or "")[:32]
        summary = html.escape(clean_summary(item.get("summary") or ""))
        tag   = item.get("tag", "NEWS")
        badge = tag_badge(tag)
        cards_html += f"""
<div class="card{error_class}" data-tag="{tag}">
  <div class="card-top">
    {badge}
    <div class="card-title"><a href="{link}" target="_blank" rel="noopener">{title}</a></div>
  </div>
  <div class="card-meta"><span class="source">{source}</span>{' · ' + pub if pub else ''}</div>
  {'<div class="summary">' + summary + '</div>' if summary else ''}
</div>"""

    return HTML_TEMPLATE.format(
        timestamp=timestamp,
        total=len(all_items),
        sources=len(sources_seen),
        filter_buttons=filter_buttons,
        stat_cards=stat_cards,
        cards=cards_html,
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🛡  IT Security Feed Aggregator")
    print(f"    Fetching from {len(FEEDS)} sources...\n")

    all_items = []
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fetch_feed, feed): feed for feed in FEEDS}
        for future in as_completed(futures):
            feed = futures[future]
            results = future.result()
            ok = [r for r in results if not r.get("error")]
            err = [r for r in results if r.get("error")]
            status = f"✓ {len(ok):>2} items" if ok else "✗ failed "
            print(f"  [{feed['tag']:>8}] {status}  ← {feed['name']}")
            all_items.extend(results)

    # Sort: errors last, then by publication date desc
    def sort_key(item):
        if item.get("error"):
            return ""
        return item.get("pub") or ""

    all_items.sort(key=sort_key, reverse=True)

    print(f"\n  Total: {len(all_items)} items in {time.time()-t0:.1f}s")

    # Render HTML
    html_content = render_html(all_items)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security_feed.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n  ✅ Saved → {out_path}")
    print(f"  🌐 Opening in browser...")
    webbrowser.open(f"file://{out_path}")

if __name__ == "__main__":
    main()
