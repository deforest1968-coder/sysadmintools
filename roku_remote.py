#!/usr/bin/env python3
import http.server
import urllib.request
import urllib.parse
import urllib.error
import threading
import webbrowser
import time
import socket
import json
import concurrent.futures

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roku Remote</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --surface: #ffffff;
    --surface2: #eef0f4;
    --border: rgba(0,0,0,0.09);
    --border2: rgba(0,0,0,0.15);
    --text: #111114;
    --muted: #55556a;
    --mono: 'DM Mono', monospace;
    --sans: 'Space Grotesk', sans-serif;
  }

  body {
    background: linear-gradient(150deg, #020c1e 0%, #041538 25%, #081d55 50%, #0b0e50 70%, #04060f 100%);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem 1rem 5rem;
  }

  .remote {
    width: 100%;
    max-width: 340px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .card {
    background: var(--surface);
    border-radius: 16px;
    padding: 14px;
    border: 1px solid rgba(255,255,255,0.12);
    box-shadow: 0 2px 12px rgba(0,0,0,0.18);
  }

  .card-connect { border-top: 3px solid #4f83f7; }
  .card-system  { border-top: 3px solid #e25d3b; }
  .card-nav     { border-top: 3px solid #9b59e8; }
  .card-play    { border-top: 3px solid #17a589; }
  .card-vol     { border-top: 3px solid #e8a317; }
  .card-apps    { border-top: 3px solid #e84393; }
  .card-search  { border-top: 3px solid #3dbf6e; }
  .card-nowplaying { border-top: 3px solid #f59e0b; }

  .nowplaying-idle { color: var(--muted); font-size: 13px; font-family: var(--mono); }

  .np-app {
    font-size: 11px; font-family: var(--mono); letter-spacing: 0.1em;
    text-transform: uppercase; color: #b45309; margin-bottom: 6px;
  }
  .np-title {
    font-size: 16px; font-weight: 600; color: var(--text);
    margin-bottom: 2px; line-height: 1.3;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .np-meta {
    font-size: 12px; font-family: var(--mono); color: var(--muted);
    margin-bottom: 10px; display: flex; align-items: center; gap: 8px;
  }
  .np-state {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; font-family: var(--mono);
    padding: 2px 7px; border-radius: 20px;
    background: #fef3c7; color: #92400e; border: 1px solid #fcd49a;
  }
  .np-state.playing { background: #ecfdf5; color: #166534; border-color: #86efac; }
  .np-state.paused  { background: #eff6ff; color: #1e40af; border-color: #bfdbfe; }
  .np-state.buffering { background: #faf5ff; color: #6b21a8; border-color: #d8b4fe; }

  .np-progress-wrap { margin-top: 8px; }
  .np-times { display: flex; justify-content: space-between; font-size: 11px; font-family: var(--mono); color: var(--muted); margin-bottom: 4px; }
  .np-bar-bg { height: 5px; background: #e5e7eb; border-radius: 99px; overflow: hidden; }
  .np-bar-fill { height: 100%; background: linear-gradient(90deg, #f59e0b, #ef4444); border-radius: 99px; transition: width 1s linear; width: 0%; }

  .section-label {
    font-size: 10px;
    font-family: var(--mono);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 10px;
    font-weight: 500;
  }

  /* Device picker */
  .device-row { display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }

  /* Custom dropdown */
  .custom-select { flex: 1; position: relative; }
  .custom-select-trigger {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 8px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    padding: 8px 30px 8px 12px;
    cursor: pointer;
    display: flex; align-items: center;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    user-select: none;
    transition: border-color 0.2s;
  }
  .custom-select-trigger:hover { border-color: #4f83f7; }
  .custom-select-trigger .arrow {
    position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
    pointer-events: none; color: var(--muted);
  }
  .custom-select-options {
    display: none;
    position: absolute; top: calc(100% + 4px); left: 0; right: 0;
    background: #ffffff;
    border: 1px solid var(--border2);
    border-radius: 8px;
    z-index: 100;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    overflow: hidden;
  }
  .custom-select.open .custom-select-options { display: block; }
  .custom-select-option {
    padding: 9px 12px;
    font-family: var(--mono);
    font-size: 13px;
    color: var(--text);
    cursor: pointer;
    transition: background 0.1s;
  }
  .custom-select-option:hover { background: #eef2ff; color: #1a56db; }
  .custom-select-option.selected { background: #eef2ff; color: #1a56db; font-weight: 500; }
  .custom-select-option.placeholder { color: var(--muted); }

  .scan-btn {
    background: #eef2ff; border: 1px solid #bfcfff;
    border-radius: 8px; color: #1a56db;
    font-size: 12px; font-weight: 500;
    cursor: pointer; padding: 8px 12px;
    font-family: var(--mono); transition: all 0.15s;
    flex-shrink: 0; white-space: nowrap;
  }
  .scan-btn:hover { background: #dde5ff; }
  .scan-btn:active { transform: scale(0.96); }
  .scan-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .connect-btn {
    background: #eef2ff; border: 1px solid #bfcfff;
    border-radius: 8px; color: #1a56db;
    font-size: 13px; font-weight: 500;
    cursor: pointer; padding: 8px 14px;
    font-family: var(--sans); transition: all 0.15s;
    flex-shrink: 0;
  }
  .connect-btn:hover { background: #dde5ff; }
  .connect-btn:active { transform: scale(0.96); }

  /* Status */
  .status { display: flex; align-items: center; gap: 10px; }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #bbb; flex-shrink: 0; transition: background 0.3s;
  }
  .dot.ok  { background: #22c97a; box-shadow: 0 0 7px #22c97a88; }
  .dot.err { background: #e25d3b; box-shadow: 0 0 7px #e25d3b66; }
  .dot.scanning { background: #4f83f7; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .status-text { font-size: 14px; color: var(--muted); flex: 1; }

  input[type=text] {
    flex: 1;
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 8px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    padding: 8px 12px;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type=text]:focus { border-color: #4f83f7; }

  .btn {
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 10px;
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    padding: 10px 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 5px;
    transition: background 0.15s, transform 0.1s;
    user-select: none;
    line-height: 1;
  }
  .btn:hover { background: #dde0e8; }
  .btn:active { transform: scale(0.92); }
  .btn svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .btn .lbl { font-size: 10px; color: var(--muted); font-family: var(--mono); font-weight: 400; }

  .btn-home  { color: #1a56db; border-color: #bfcfff; background: #eef2ff; }
  .btn-home:hover { background: #dde5ff; }
  .btn-back  { color: #555; }
  .btn-power { color: #c0392b; border-color: #fbbcbc; background: #fff0f0; }
  .btn-power:hover { background: #ffe0e0; }
  .btn-nav { color: #7c3aed; border-color: #d8c8ff; background: #f5f0ff; }
  .btn-nav:hover { background: #ede5ff; }
  .dpad-ok {
    background: #7c3aed; color: #fff;
    border: none; border-radius: 50%;
    width: 100%; aspect-ratio: 1;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 13px; font-weight: 600;
    font-family: var(--mono); transition: background 0.15s, transform 0.1s;
  }
  .dpad-ok:hover { background: #6d28d9; }
  .dpad-ok:active { transform: scale(0.92); }
  .btn-play { color: #0e7490; border-color: #a5d8e6; background: #ecfbfd; }
  .btn-play:hover { background: #d5f3f9; }
  .btn-vol { color: #92400e; border-color: #fcd49a; background: #fffbeb; }
  .btn-vol:hover { background: #fef3c7; }

  .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 7px; }
  .grid5 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 7px; }

  .dpad {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
    max-width: 190px;
    margin: 0 auto;
  }
  .dpad-blank { visibility: hidden; }

  .apps { display: flex; flex-wrap: wrap; gap: 6px; }
  .app-chip {
    background: #fff0f6; border: 1px solid #f9b8d4;
    border-radius: 20px; padding: 6px 13px;
    font-size: 13px; color: #9d174d;
    cursor: pointer; transition: all 0.15s; font-family: var(--mono);
  }
  .app-chip:hover { background: #fce7f3; border-color: #e84393; color: #be185d; }
  .app-chip:active { transform: scale(0.95); }

  .search-row { display: flex; gap: 8px; }
  .search-btn {
    background: #ecfdf5; border: 1px solid #86efac;
    border-radius: 8px; color: #166534;
    cursor: pointer; padding: 8px 16px;
    font-size: 13px; font-weight: 500;
    font-family: var(--mono); transition: all 0.15s; flex-shrink: 0;
  }
  .search-btn:hover { background: #dcfce7; }
  .search-btn:active { transform: scale(0.96); }

  #toast {
    position: fixed; bottom: 1.5rem; left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: rgba(10,15,40,0.92);
    border: 1px solid rgba(120,160,255,0.2);
    border-radius: 8px; padding: 8px 18px;
    font-size: 12px; font-family: var(--mono);
    color: #a0c0ff; opacity: 0;
    transition: all 0.25s; pointer-events: none; white-space: nowrap;
  }
  #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>

<div class="remote">

  <!-- Connection -->
  <div class="card card-connect">
    <div class="section-label">Device</div>
    <div class="device-row">
      <div class="custom-select" id="custom-select">
        <div class="custom-select-trigger" id="select-trigger" onclick="toggleDropdown()">
          <span id="select-label">— scan to discover —</span>
          <span class="arrow">&#9662;</span>
        </div>
        <div class="custom-select-options" id="select-options"></div>
      </div>
      <button class="scan-btn" id="scan-btn" onclick="scan()">Scan</button>
    </div>
    <div class="status">
      <div class="dot" id="dot"></div>
      <span class="status-text" id="st">Not connected</span>

    </div>
  </div>

  <!-- Now Playing -->
  <div class="card card-nowplaying" id="np-card">
    <div class="section-label">Now Playing</div>
    <div class="nowplaying-idle" id="np-idle">No device connected</div>
    <div id="np-content" style="display:none">
      <div class="np-app" id="np-app"></div>
      <div class="np-title" id="np-title"></div>
      <div class="np-meta">
        <span class="np-state" id="np-state"></span>
        <span id="np-extra"></span>
      </div>
      <div class="np-progress-wrap" id="np-progress-wrap" style="display:none">
        <div class="np-times"><span id="np-pos">0:00</span><span id="np-dur">0:00</span></div>
        <div class="np-bar-bg"><div class="np-bar-fill" id="np-bar"></div></div>
      </div>
    </div>
  </div>

  <!-- System -->
  <div class="card card-system">
    <div class="section-label">System</div>
    <div class="grid3">
      <button class="btn btn-home" onclick="key('Home')">
        <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <span class="lbl">Home</span>
      </button>
      <button class="btn btn-back" onclick="key('Back')">
        <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>
        <span class="lbl">Back</span>
      </button>
      <button class="btn btn-power" onclick="key('PowerOff')">
        <svg viewBox="0 0 24 24"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
        <span class="lbl">Power</span>
      </button>
    </div>
  </div>

  <!-- D-pad -->
  <div class="card card-nav">
    <div class="section-label">Navigate</div>
    <div class="dpad">
      <div class="dpad-blank"></div>
      <button class="btn btn-nav" onclick="key('Up')">
        <svg viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"/></svg>
      </button>
      <div class="dpad-blank"></div>
      <button class="btn btn-nav" onclick="key('Left')">
        <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="dpad-ok" onclick="key('Select')" role="button">OK</div>
      <button class="btn btn-nav" onclick="key('Right')">
        <svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
      <div class="dpad-blank"></div>
      <button class="btn btn-nav" onclick="key('Down')">
        <svg viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div class="dpad-blank"></div>
    </div>
  </div>

  <!-- Playback -->
  <div class="card card-play">
    <div class="section-label">Playback</div>
    <div class="grid5">
      <button class="btn btn-play" onclick="key('Rev')">
        <svg viewBox="0 0 24 24"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/></svg>
        <span class="lbl">Rew</span>
      </button>
      <button class="btn btn-play" onclick="key('Play')">
        <svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        <span class="lbl">Play</span>
      </button>
      <button class="btn btn-play" onclick="key('Pause')">
        <svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        <span class="lbl">Pause</span>
      </button>
      <button class="btn btn-play" onclick="key('Fwd')">
        <svg viewBox="0 0 24 24"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>
        <span class="lbl">Fwd</span>
      </button>
      <button class="btn btn-play" onclick="key('InstantReplay')">
        <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3"/></svg>
        <span class="lbl">Replay</span>
      </button>
    </div>
  </div>

  <!-- Volume -->
  <div class="card card-vol">
    <div class="section-label">Volume</div>
    <div class="grid3">
      <button class="btn btn-vol" onclick="key('VolumeUp')">
        <svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        <span class="lbl">Vol +</span>
      </button>
      <button class="btn btn-vol" onclick="key('VolumeMute')">
        <svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
        <span class="lbl">Mute</span>
      </button>
      <button class="btn btn-vol" onclick="key('VolumeDown')">
        <svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="12" x2="17" y2="12"/></svg>
        <span class="lbl">Vol –</span>
      </button>
    </div>
  </div>

  <!-- Apps -->
  <div class="card card-apps">
    <div class="section-label">Apps</div>
    <div class="apps">
      <div class="app-chip" onclick="launch(12)">Netflix</div>
      <div class="app-chip" onclick="launch('tvinput_youtube')">YouTube</div>
      <div class="app-chip" onclick="launch(2285)">Hulu</div>
      <div class="app-chip" onclick="launch(13)">Prime</div>
      <div class="app-chip" onclick="launch(2553)">Disney+</div>
      <div class="app-chip" onclick="launch(31440)">Peacock</div>
      <div class="app-chip" onclick="launch(34399)">Max</div>
      <div class="app-chip" onclick="launchInput('hdmi1')">HDMI 1</div>
      <div class="app-chip" onclick="launchInput('hdmi2')">HDMI 2</div>
    </div>
  </div>

  <!-- Search -->
  <div class="card card-search">
    <div class="section-label">Search</div>
    <div class="search-row">
      <input type="text" id="q" placeholder="Search for a show…" onkeydown="if(event.key==='Enter')search()" />
      <button class="search-btn" onclick="search()">Go</button>
    </div>
  </div>

</div>

<div id="toast"></div>

<script>
  const BASE = 'http://localhost:8888';
  let currentIP = null;

  function ip() { return currentIP; }

  function setStatus(msg, state, np) {
    document.getElementById('dot').className = 'dot' + (state ? ' ' + state : '');
    document.getElementById('st').textContent = msg;
    if (np !== undefined) document.getElementById('np').textContent = np;
  }

  function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), 2000);
  }

  let devices = [];
  let selectedIP = null;

  function toggleDropdown() {
    const cs = document.getElementById('custom-select');
    cs.classList.toggle('open');
    // close on outside click
    if (cs.classList.contains('open')) {
      setTimeout(() => document.addEventListener('click', closeDropdownOutside), 0);
    }
  }

  function closeDropdownOutside(e) {
    const cs = document.getElementById('custom-select');
    if (!cs.contains(e.target)) {
      cs.classList.remove('open');
      document.removeEventListener('click', closeDropdownOutside);
    }
  }

  function renderOptions(list, placeholder) {
    const container = document.getElementById('select-options');
    const label = document.getElementById('select-label');
    container.innerHTML = '';
    if (placeholder) {
      const ph = document.createElement('div');
      ph.className = 'custom-select-option placeholder';
      ph.textContent = placeholder;
      container.appendChild(ph);
      label.textContent = placeholder;
      return;
    }
    list.forEach((d, i) => {
      const opt = document.createElement('div');
      opt.className = 'custom-select-option' + (i === 0 ? ' selected' : '');
      opt.textContent = `${d.name} (${d.ip})`;
      opt.onclick = () => {
        document.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        label.textContent = opt.textContent;
        document.getElementById('custom-select').classList.remove('open');
        document.removeEventListener('click', closeDropdownOutside);
        currentIP = d.ip;
        connect();
      };
      container.appendChild(opt);
    });
    if (list.length > 0) {
      label.textContent = `${list[0].name} (${list[0].ip})`;
    }
  }

  async function scan() {
    const btn = document.getElementById('scan-btn');
    btn.disabled = true;
    btn.textContent = 'Scanning…';
    setStatus('Scanning 10.0.0.0/24…', 'scanning');
    renderOptions([], 'Scanning…');

    try {
      const r = await fetch(`${BASE}/scan`);
      devices = await r.json();
      if (devices.length === 0) {
        renderOptions([], 'No Roku devices found');
        setStatus('No devices found', 'err');
      } else {
        renderOptions(devices);
        currentIP = devices[0].ip;
        await connect();
      }
    } catch {
      setStatus('Scan failed', 'err');
      renderOptions([], 'Scan failed');
    }

    btn.disabled = false;
    btn.textContent = 'Scan';
  }

  async function connect() {
    if (!currentIP) return;
    setStatus('Connecting…', '');
    try {
      const r = await fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/query/device-info')}`);
      if (!r.ok) throw new Error();
      const xml = await r.text();
      const name = xml.match(/<friendly-device-name>(.*?)<\/friendly-device-name>/)?.[1] || 'Roku';
      setStatus(name + ' — connected', 'ok');
      pollApp();
    } catch {
      setStatus('Could not reach device', 'err');
    }
  }

  function fmtTime(ms) {
    if (!ms || isNaN(ms)) return '';
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const ss = String(s % 60).padStart(2, '0');
    const mm = String(m % 60).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
  }

  async function pollApp() {
    if (!currentIP) return;
    try {
      // Fetch active app and media player in parallel
      const [appResp, mediaResp] = await Promise.all([
        fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/query/active-app')}`),
        fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/query/media-player')}`)
      ]);

      const appXml = await appResp.text();
      const mediaXml = await mediaResp.text();

      const appName = appXml.match(/<app[^>]*>([^<]+)<\/app>/)?.[1] || '';
      const isHome = !appName || appName === 'Roku';

      const idle = document.getElementById('np-idle');
      const content = document.getElementById('np-content');

      if (isHome) {
        idle.textContent = 'On home screen';
        idle.style.display = '';
        content.style.display = 'none';
        return;
      }

      // Parse media-player XML
      const state    = mediaXml.match(/<state>(.*?)<\/state>/)?.[1] || '';
      const title    = mediaXml.match(/<title>(.*?)<\/title>/)?.[1] || '';
      const posMs    = parseInt(mediaXml.match(/<position>(\d+)/)?.[1] || '0');
      const durMs    = parseInt(mediaXml.match(/<duration>(\d+)/)?.[1] || '0');
      const runtime  = mediaXml.match(/<runtime>(.*?)<\/runtime>/)?.[1] || '';

      idle.style.display = 'none';
      content.style.display = '';

      document.getElementById('np-app').textContent = appName;
      document.getElementById('np-title').textContent = title || appName;

      // State badge
      const stateEl = document.getElementById('np-state');
      stateEl.className = 'np-state ' + (state || '');
      const stateLabels = { play: '▶ Playing', pause: '⏸ Paused', buffer: '⏳ Buffering', close: '◼ Stopped' };
      stateEl.textContent = stateLabels[state] || (state || '—');

      // Progress
      const progWrap = document.getElementById('np-progress-wrap');
      if (durMs > 0 && posMs >= 0) {
        progWrap.style.display = '';
        document.getElementById('np-pos').textContent = fmtTime(posMs);
        document.getElementById('np-dur').textContent = fmtTime(durMs);
        const pct = Math.min(100, (posMs / durMs) * 100).toFixed(1);
        document.getElementById('np-bar').style.width = pct + '%';
      } else {
        progWrap.style.display = 'none';
      }

    } catch {}
    // Poll every 5 seconds while connected
    setTimeout(pollApp, 5000);
  }

  async function key(k) {
    if (!currentIP) { toast('No device selected'); return; }
    try {
      await fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/keypress/' + k)}&method=POST`);
      toast(k);
    } catch { setStatus('Command failed', 'err'); }
  }

  async function launch(id) {
    if (!currentIP) { toast('No device selected'); return; }
    try {
      await fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/launch/' + id)}&method=POST`);
      toast('Launching…');
      setTimeout(pollApp, 3000);
    } catch { setStatus('Launch failed', 'err'); }
  }

  function launchInput(hdmi) { launch('tvinput.' + hdmi); }

  async function search() {
    if (!currentIP) { toast('No device selected'); return; }
    const q = document.getElementById('q').value.trim();
    if (!q) return;
    try {
      await fetch(`${BASE}/proxy?url=${encodeURIComponent('http://' + currentIP + ':8060/search/browse?keyword=' + encodeURIComponent(q) + '&type=series')}&method=POST`);
      toast('Searching: ' + q);
    } catch { setStatus('Search failed', 'err'); }
  }

  // Auto-scan on load
  window.addEventListener('load', () => setTimeout(scan, 400));
</script>
</body>
</html>
"""

def check_roku(ip):
    """Try port 8060 on the given IP, return device info if it's a Roku."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((ip, 8060))
        sock.close()
        if result != 0:
            return None
        # Port open — fetch device info
        url = f'http://{ip}:8060/query/device-info'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2) as resp:
            xml = resp.read().decode('utf-8', errors='ignore')
        import re
        name_match = re.search(r'<friendly-device-name>(.*?)</friendly-device-name>', xml)
        name = name_match.group(1) if name_match else f'Roku @ {ip}'
        return {'ip': ip, 'name': name}
    except Exception:
        return None

def scan_network():
    """Scan 10.0.0.1-254 for Roku devices in parallel."""
    ips = [f'10.0.0.{i}' for i in range(1, 255)]
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
        results = ex.map(check_roku, ips)
    for r in results:
        if r:
            found.append(r)
    found.sort(key=lambda d: int(d['ip'].split('.')[-1]))
    return found

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/scan':
            devices = scan_network()
            body = json.dumps(devices).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == '/proxy':
            url = params.get('url', [''])[0]
            method = params.get('method', ['GET'])[0].upper()
            if not url:
                self.send_error(400, 'Missing url param')
                return
            try:
                req = urllib.request.Request(url, method=method)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/xml; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except urllib.error.URLError as e:
                self.send_response(502)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(str(e).encode())

        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def log_message(self, fmt, *args):
        pass

PORT = 8888

def open_browser():
    time.sleep(0.8)
    webbrowser.open(f'http://localhost:{PORT}')

if __name__ == '__main__':
    server = http.server.HTTPServer(('localhost', PORT), Handler)
    threading.Thread(target=open_browser, daemon=True).start()
    print(f'Roku remote running at http://localhost:{PORT}')
    print('Scanning 10.0.0.0/24 for Roku devices on connect…')
    print('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
