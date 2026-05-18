#!/usr/bin/env python3
"""
image_finder.py — local image search tool
Spawns a browser UI to search images via DuckDuckGo, renders thumbnails,
and lets you save any image locally with one click.

Usage:
    python image_finder.py [--port 8765]

Requirements:
    pip install requests
"""

import argparse
import http.server
import json
import os
import re
import socketserver
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# ── DuckDuckGo image scraper (no API key needed) ───────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def ddg_search(query: str, max_results: int = 40) -> list[dict]:
    """Return a list of image dicts from DuckDuckGo."""
    token_url = (
        "https://duckduckgo.com/?q="
        + urllib.parse.quote(query)
        + "&iax=images&ia=images"
    )
    req = urllib.request.Request(token_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    vqd_match = re.search(r'vqd=(["\'])([^"\']+)\1', html)
    if not vqd_match:
        vqd_match = re.search(r'vqd=([\d-]+)', html)
        vqd = vqd_match.group(1) if vqd_match else ""
    else:
        vqd = vqd_match.group(2)

    if not vqd:
        return []

    api_url = (
        "https://duckduckgo.com/i.js?l=us-en&o=json&q="
        + urllib.parse.quote(query)
        + "&vqd=" + urllib.parse.quote(vqd)
        + "&f=,,,,,&p=1"
    )
    req2 = urllib.request.Request(api_url, headers={**HEADERS, "Referer": token_url})
    with urllib.request.urlopen(req2, timeout=10) as resp2:
        data = json.loads(resp2.read())

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "thumb": item.get("thumbnail", ""),
            "url":   item.get("image", ""),
            "title": item.get("title", ""),
            "width": item.get("width", 0),
            "height": item.get("height", 0),
            "source": item.get("url", ""),
        })
    return results


# ── HTML page ──────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image Finder</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0d0d0f;
    --surface: #16161a;
    --border: #2a2a32;
    --accent: #c8f04a;
    --accent2: #4af0c8;
    --text: #e8e8ec;
    --muted: #6b6b7a;
    --danger: #f04a6a;
    --radius: 6px;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    padding: 0 0 60px;
  }

  /* header */
  header {
    padding: 32px 40px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: baseline;
    gap: 20px;
    position: sticky;
    top: 0;
    background: rgba(13,13,15,0.94);
    backdrop-filter: blur(8px);
    z-index: 100;
  }
  header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 1.6rem;
    color: var(--accent);
    letter-spacing: -0.5px;
    white-space: nowrap;
  }
  .search-row {
    display: flex;
    flex: 1;
    gap: 10px;
    max-width: 720px;
  }
  #query {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: inherit;
    font-size: 0.92rem;
    padding: 10px 14px;
    outline: none;
    transition: border-color .2s;
  }
  #query:focus { border-color: var(--accent); }
  #query::placeholder { color: var(--muted); }

  button {
    font-family: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    border: none;
    border-radius: var(--radius);
    padding: 10px 18px;
    transition: opacity .15s, transform .1s;
  }
  button:active { transform: scale(0.97); }

  #searchBtn {
    background: var(--accent);
    color: #0d0d0f;
    font-weight: 500;
    letter-spacing: 0.04em;
  }
  #searchBtn:hover { opacity: 0.88; }

  /* status bar */
  #status {
    padding: 10px 40px;
    font-size: 0.78rem;
    color: var(--muted);
    min-height: 36px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .spinner {
    width: 14px; height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    display: none;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* grid */
  #grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px;
    padding: 20px 40px;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: border-color .2s, transform .2s;
    animation: fadeIn .35s ease both;
  }
  .card:hover {
    border-color: var(--accent2);
    transform: translateY(-3px);
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .thumb-wrap {
    position: relative;
    aspect-ratio: 4/3;
    background: #111;
    overflow: hidden;
    cursor: zoom-in;
  }
  .thumb-wrap img {
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
    transition: transform .3s;
  }
  .card:hover .thumb-wrap img { transform: scale(1.05); }

  .dim-badge {
    position: absolute;
    bottom: 6px; right: 6px;
    background: rgba(0,0,0,.65);
    color: var(--muted);
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 3px;
    pointer-events: none;
  }

  .card-body {
    padding: 10px 12px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
  }
  .card-title {
    font-size: 0.75rem;
    color: var(--text);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.4;
  }
  .card-actions {
    display: flex;
    gap: 6px;
    margin-top: auto;
  }
  .btn-save {
    flex: 1;
    background: var(--accent);
    color: #0d0d0f;
    font-size: 0.75rem;
    padding: 7px 10px;
  }
  .btn-save:hover { opacity: 0.85; }
  .btn-save.saving { background: var(--accent2); }
  .btn-save.saved  { background: #2a2a32; color: var(--muted); cursor: default; }
  .btn-open {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.75rem;
    padding: 7px 10px;
  }
  .btn-open:hover { border-color: var(--text); color: var(--text); }

  /* lightbox */
  #lb {
    display: none;
    position: fixed; inset: 0;
    background: rgba(0,0,0,.88);
    z-index: 200;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
  }
  #lb.open { display: flex; }
  #lb img {
    max-width: 90vw;
    max-height: 90vh;
    object-fit: contain;
    border-radius: 4px;
    box-shadow: 0 0 60px rgba(0,0,0,.8);
    pointer-events: none;
  }
  #lb-close {
    position: fixed;
    top: 18px; right: 24px;
    font-size: 1.6rem;
    color: var(--muted);
    cursor: pointer;
    line-height: 1;
    background: none;
    padding: 4px 8px;
  }
  #lb-close:hover { color: var(--text); }

  /* save folder notice */
  #folder-line {
    padding: 0 40px 4px;
    font-size: 0.72rem;
    color: var(--muted);
  }
  #folder-line span { color: var(--accent2); }

  /* empty/error states */
  .empty {
    grid-column: 1/-1;
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
    font-size: 0.9rem;
  }
</style>
</head>
<body>

<header>
  <h1>⌖ ImageFinder</h1>
  <div class="search-row">
    <input id="query" type="text" placeholder="describe what you're looking for…" autofocus>
    <button id="searchBtn" onclick="doSearch()">Search</button>
  </div>
</header>

<div id="status"><div class="spinner" id="spinner"></div><span id="statusText">Ready.</span></div>
<div id="folder-line">Saves → <span id="folderLabel">…</span></div>

<div id="grid"></div>

<div id="lb" onclick="closeLB()">
  <button id="lb-close" onclick="closeLB()">✕</button>
  <img id="lb-img" src="" alt="">
</div>

<script>
const SAVE_DIR_KEY = 'imgfinder_savedir';

async function doSearch() {
  const q = document.getElementById('query').value.trim();
  if (!q) return;
  setStatus('Searching…', true);
  document.getElementById('grid').innerHTML = '';

  try {
    const r = await fetch('/search?q=' + encodeURIComponent(q));
    const data = await r.json();
    if (data.error) { setStatus('Error: ' + data.error, false); return; }
    renderGrid(data.results);
    setStatus(data.results.length
      ? `${data.results.length} images found for "${q}"`
      : `No results for "${q}"`, false);
  } catch(e) {
    setStatus('Request failed: ' + e.message, false);
  }
}

function renderGrid(results) {
  const grid = document.getElementById('grid');
  if (!results.length) {
    grid.innerHTML = '<div class="empty">No images found. Try a different query.</div>';
    return;
  }
  results.forEach((img, i) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.animationDelay = (i * 30) + 'ms';
    card.innerHTML = `
      <div class="thumb-wrap" onclick="openLB('${esc(img.url)}')">
        <img src="${esc(img.thumb)}" alt="${esc(img.title)}" loading="lazy"
             onerror="this.closest('.card').style.display='none'">
        ${img.width ? `<div class="dim-badge">${img.width}×${img.height}</div>` : ''}
      </div>
      <div class="card-body">
        <div class="card-title" title="${esc(img.title)}">${esc(img.title) || '(untitled)'}</div>
        <div class="card-actions">
          <button class="btn-save" onclick="saveImage(this,'${esc(img.url)}','${esc(img.title)}')">⬇ Save</button>
          <button class="btn-open" onclick="window.open('${esc(img.source||img.url)}','_blank')">↗</button>
        </div>
      </div>`;
    grid.appendChild(card);
  });
}

async function saveImage(btn, url, title) {
  if (btn.classList.contains('saved')) return;
  btn.textContent = '…';
  btn.classList.add('saving');
  try {
    const r = await fetch('/save', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url, title})
    });
    const data = await r.json();
    if (data.ok) {
      btn.textContent = '✓ Saved';
      btn.classList.remove('saving');
      btn.classList.add('saved');
      document.getElementById('folderLabel').textContent = data.folder;
    } else {
      btn.textContent = '✗ Error';
      btn.classList.remove('saving');
      alert('Save failed: ' + data.error);
    }
  } catch(e) {
    btn.textContent = '✗ Fail';
    btn.classList.remove('saving');
  }
}

function openLB(url) {
  document.getElementById('lb-img').src = url;
  document.getElementById('lb').classList.add('open');
}
function closeLB() {
  document.getElementById('lb').classList.remove('open');
  document.getElementById('lb-img').src = '';
}
document.addEventListener('keydown', e => { if (e.key==='Escape') closeLB(); });
document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

function setStatus(msg, loading) {
  document.getElementById('statusText').textContent = msg;
  document.getElementById('spinner').style.display = loading ? 'block' : 'none';
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// init: fetch save folder from server
fetch('/info').then(r=>r.json()).then(d=>{
  document.getElementById('folderLabel').textContent = d.save_dir;
});
</script>
</body>
</html>"""


# ── HTTP request handler ───────────────────────────────────────────────────

SAVE_DIR = Path.home() / "Pictures" / "ImageFinder"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/search":
            q = params.get("q", [""])[0].strip()
            if not q:
                self.send_json({"error": "empty query"}, 400)
                return
            try:
                results = ddg_search(q)
                self.send_json({"results": results})
            except Exception as ex:
                self.send_json({"error": str(ex)}, 500)

        elif path == "/info":
            self.send_json({"save_dir": str(SAVE_DIR)})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/save":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            url    = body.get("url", "").strip()
            title  = body.get("title", "image").strip()

            if not url:
                self.send_json({"ok": False, "error": "no url"}, 400)
                return

            try:
                SAVE_DIR.mkdir(parents=True, exist_ok=True)

                # build filename
                ext = os.path.splitext(urllib.parse.urlparse(url).path)[-1]
                if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"):
                    ext = ".jpg"
                safe = re.sub(r'[^\w\- ]', '', title)[:60].strip() or "image"
                # avoid collisions
                base = SAVE_DIR / (safe + ext)
                n = 1
                while base.exists():
                    base = SAVE_DIR / f"{safe}_{n}{ext}"
                    n += 1

                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                base.write_bytes(data)
                self.send_json({"ok": True, "path": str(base), "folder": str(SAVE_DIR)})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
        else:
            self.send_response(404)
            self.end_headers()


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Local image search + save tool")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--save-dir", type=str, default=None, help="Directory to save images (default: ~/Pictures/ImageFinder)")
    args = parser.parse_args()

    global SAVE_DIR
    if args.save_dir:
        SAVE_DIR = Path(args.save_dir).expanduser().resolve()

    url = f"http://localhost:{args.port}"
    print(f"\n  ImageFinder running → {url}")
    print(f"  Images saved to    → {SAVE_DIR}")
    print(f"  Press Ctrl+C to quit\n")

    # open browser after short delay so server is ready
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    with socketserver.TCPServer(("", args.port), Handler) as srv:
        srv.allow_reuse_address = True
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n  Shutting down.")

if __name__ == "__main__":
    main()
