#!/usr/bin/env python3
"""
net_scanner_server.py
─────────────────────
Real network scanner + packet sniffer with a live HTML dashboard.

Requirements:
    pip install scapy websockets

Run as root (needed for ARP + raw packet capture):
    sudo python3 net_scanner_server.py

Opens http://localhost:8888 automatically in your default browser.
WebSocket data streams on ws://localhost:8765
"""

import asyncio
import ipaddress
import json
import os
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── dependency check ──────────────────────────────────────────────
try:
    import websockets
except ImportError:
    print("websockets not installed.  Run:  pip install websockets")
    sys.exit(1)

try:
    from scapy.all import ARP, Ether, srp, sniff, IP, TCP, UDP, ICMP, DNS
except ImportError:
    print("scapy not installed.  Run:  pip install scapy")
    sys.exit(1)

# ── config ────────────────────────────────────────────────────────
NETWORK      = "10.0.0.0/24"
SCAN_TIMEOUT = 2
WS_PORT      = 8765
HTTP_PORT    = 8888
MAX_TRAFFIC  = 500

# ── shared state ──────────────────────────────────────────────────
live_hosts   = []        # [{ip, mac}]
traffic_log  = deque(maxlen=MAX_TRAFFIC)
sniff_target = None
scan_done    = False
sniff_thread = None
lock         = threading.Lock()
ws_clients   = set()    # connected WebSocket clients


# ═════════════════════════════════════════════════════════════════
# ARP Scanner
# ═════════════════════════════════════════════════════════════════
def arp_scan():
    global scan_done
    net = ipaddress.IPv4Network(NETWORK, strict=False)
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(net))
    answered, _ = srp(pkt, timeout=SCAN_TIMEOUT, verbose=False)
    with lock:
        for _, rcv in answered:
            ip  = rcv[ARP].psrc
            mac = rcv[Ether].src
            if ip not in [h["ip"] for h in live_hosts]:
                live_hosts.append({"ip": ip, "mac": mac})
        live_hosts.sort(key=lambda h: ipaddress.IPv4Address(h["ip"]))
    scan_done = True
    broadcast_sync({"type": "scan_done", "hosts": live_hosts})


# ═════════════════════════════════════════════════════════════════
# Packet Classifier
# ═════════════════════════════════════════════════════════════════
def classify_packet(pkt):
    if TCP in pkt:
        sp, dp = pkt[TCP].sport, pkt[TCP].dport
        flags  = pkt[TCP].sprintf("%flags%")
        if dp in (80, 8080) or sp in (80, 8080):
            proto = "HTTP"
        elif dp == 443 or sp == 443:
            proto = "TLS"
        elif dp == 22 or sp == 22:
            proto = "SSH"
        elif dp == 21 or sp == 21:
            proto = "FTP"
        elif dp == 25 or sp == 25:
            proto = "SMTP"
        else:
            proto = "TCP"
        detail = f"port {sp} → {dp}  [{flags}]"
    elif UDP in pkt:
        sp, dp = pkt[UDP].sport, pkt[UDP].dport
        if DNS in pkt:
            proto = "DNS"
            try:
                qname  = pkt[DNS].qd.qname.decode(errors="replace").rstrip(".")
                detail = f"query {qname}"
            except Exception:
                detail = f"port {sp} → {dp}"
        elif dp in (67, 68):
            proto  = "DHCP"
            detail = f"port {sp} → {dp}"
        else:
            proto  = "UDP"
            detail = f"port {sp} → {dp}"
    elif ICMP in pkt:
        t_map  = {0: "echo-reply", 8: "echo-request", 3: "unreachable", 11: "time-exceeded"}
        proto  = "ICMP"
        detail = t_map.get(pkt[ICMP].type, f"type {pkt[ICMP].type}")
    else:
        proto  = str(pkt[IP].proto) if IP in pkt else "???"
        detail = ""
    return proto, detail


def pkt_handler(pkt):
    global sniff_target
    if IP not in pkt or not sniff_target:
        return
    src, dst = pkt[IP].src, pkt[IP].dst
    if sniff_target not in (src, dst):
        return

    proto, detail = classify_packet(pkt)
    size      = len(pkt)
    ts        = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    direction = "OUT" if src == sniff_target else "IN"
    peer      = dst   if src == sniff_target else src

    entry = {"type": "packet", "ts": ts, "dir": direction,
             "peer": peer, "proto": proto, "size": size, "detail": detail}
    with lock:
        traffic_log.appendleft(entry)
    broadcast_sync(entry)


def start_sniffer():
    sniff(prn=pkt_handler, store=False, filter="ip")


# ═════════════════════════════════════════════════════════════════
# WebSocket broadcast helper (thread-safe)
# ═════════════════════════════════════════════════════════════════
_loop = None

def broadcast_sync(msg):
    """Called from non-async threads — safely schedules onto the event loop."""
    global _loop
    if _loop is None:
        return
    data = json.dumps(msg)
    asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)

async def _broadcast(data: str):
    dead = set()
    for ws in list(ws_clients):
        try:
            await ws.send(data)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ═════════════════════════════════════════════════════════════════
# WebSocket handler
# ═════════════════════════════════════════════════════════════════
async def ws_handler(websocket):
    global sniff_target, sniff_thread
    ws_clients.add(websocket)
    try:
        # Send current state immediately on connect
        with lock:
            hosts_now = list(live_hosts)
            log_now   = list(traffic_log)

        await websocket.send(json.dumps({
            "type":      "init",
            "scan_done": scan_done,
            "hosts":     hosts_now,
            "traffic":   log_now,
            "target":    sniff_target,
        }))

        async for raw in websocket:
            msg = json.loads(raw)

            if msg.get("type") == "set_target":
                ip = msg.get("ip", "").strip()
                try:
                    ipaddress.IPv4Address(ip)
                except Exception:
                    await websocket.send(json.dumps({"type": "error", "msg": f"Invalid IP: {ip}"}))
                    continue

                sniff_target = ip
                with lock:
                    traffic_log.clear()

                # Start sniffer thread if not already running
                if sniff_thread is None or not sniff_thread.is_alive():
                    sniff_thread = threading.Thread(target=start_sniffer, daemon=True)
                    sniff_thread.start()

                await _broadcast(json.dumps({"type": "target_set", "ip": ip}))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)


# ═════════════════════════════════════════════════════════════════
# Inline HTML (served by the HTTP server)
# ═════════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetScan — Live</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f0f2f5;--bg2:#e4e8ee;--surface:#fff;--border:#d0d6e0;--border2:#b8c2d0;
  --text:#1a2332;--text2:#4a5568;--text3:#8896a8;
  --accent:#1a6ef7;--accent2:#0a4fd4;
  --green:#16a34a;--green-bg:#dcfce7;--green-b:#86efac;
  --red:#dc2626;--red-bg:#fee2e2;
  --orange:#ea580c;--orange-bg:#ffedd5;
  --purple:#7c3aed;--purple-bg:#ede9fe;
  --yellow:#ca8a04;--yellow-bg:#fef9c3;
  --cyan:#0891b2;--cyan-bg:#cffafe;
  --shadow:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06);
  --shadow-md:0 4px 6px rgba(0,0,0,.07),0 2px 4px rgba(0,0,0,.06);
  --radius:8px;
  --mono:'JetBrains Mono',monospace;
  --display:'Syne',sans-serif;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;line-height:1.5}
#app{display:grid;grid-template-rows:56px 1fr 18px 1fr 44px;height:100vh;max-width:1400px;margin:0 auto;padding:0 16px}

/* header */
#header{display:flex;align-items:center;gap:16px;padding:0 4px;border-bottom:2px solid var(--border)}
.logo{font-family:var(--display);font-size:18px;font-weight:800;color:var(--accent);letter-spacing:-.5px}
.logo span{color:var(--text3);font-weight:700}
.tag{background:var(--accent);color:#fff;font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px;letter-spacing:.5px}
.tag.live{background:var(--green)}
#scan-status{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text2)}
.dot{width:8px;height:8px;border-radius:50%}
.dot.scanning{background:var(--orange);animation:ping-o 1.2s infinite}
.dot.live{background:var(--green);animation:ping-g 1.2s infinite}
.dot.idle{background:var(--text3)}
@keyframes ping-o{0%,100%{box-shadow:0 0 0 0 rgba(234,88,12,.4)}50%{box-shadow:0 0 0 6px rgba(234,88,12,0)}}
@keyframes ping-g{0%,100%{box-shadow:0 0 0 0 rgba(22,163,74,.4)}50%{box-shadow:0 0 0 6px rgba(22,163,74,0)}}

/* ws badge */
#ws-badge{font-size:10px;padding:2px 8px;border-radius:999px;font-weight:600;letter-spacing:.5px}
#ws-badge.conn{background:var(--green-bg);color:var(--green);border:1px solid var(--green-b)}
#ws-badge.disc{background:var(--red-bg);color:var(--red);border:1px solid #fca5a5}

/* panes */
.pane{display:flex;flex-direction:column;overflow:hidden;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin:8px 0 4px;box-shadow:var(--shadow-md)}
.pane-head{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--border);background:var(--bg2);border-radius:var(--radius) var(--radius) 0 0;flex-shrink:0}
.pane-title{font-family:var(--display);font-size:11px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--text)}
.pane-badge{font-size:11px;color:var(--text3);margin-left:auto}
.progress-wrap{height:3px;background:var(--bg2);flex-shrink:0;overflow:hidden}
.progress-bar{height:100%;background:linear-gradient(90deg,var(--accent),#60a5fa);width:0%;transition:width .3s ease;border-radius:0 2px 2px 0}
.col-head{display:grid;padding:6px 16px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text3);border-bottom:1px solid var(--border);background:var(--bg);flex-shrink:0}
.host-cols{grid-template-columns:44px 148px 170px 1fr 100px}
.traffic-cols{grid-template-columns:100px 50px 140px 68px 68px 1fr}

/* host list */
#host-scroll{overflow-y:auto;flex:1}
#host-scroll::-webkit-scrollbar{width:5px}
#host-scroll::-webkit-scrollbar-track{background:var(--bg)}
#host-scroll::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.host-row{display:grid;grid-template-columns:44px 148px 170px 1fr 100px;align-items:center;padding:8px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s;animation:slideIn .25s ease both}
@keyframes slideIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.host-row:last-child{border-bottom:none}
.host-row:hover{background:#f0f4ff}
.host-row.active{background:#e8f0ff;border-left:3px solid var(--accent);padding-left:13px}
.h-num{font-size:11px;color:var(--text3);font-weight:600}
.h-ip{font-weight:700;color:var(--text);font-size:13px;letter-spacing:.3px}
.host-row.active .h-ip{color:var(--accent)}
.h-mac{font-size:11px;color:var(--text2)}
.h-note{font-size:11px;color:var(--text3)}
.h-btn{background:var(--accent);color:#fff;border:none;border-radius:5px;padding:4px 10px;font-family:var(--mono);font-size:11px;font-weight:600;cursor:pointer;transition:background .15s,transform .1s;letter-spacing:.3px;white-space:nowrap}
.h-btn:hover{background:var(--accent2);transform:translateY(-1px)}
.host-row.active .h-btn{background:var(--green)}
.empty-state{padding:20px 16px;color:var(--text3);font-size:12px;display:flex;align-items:center;gap:8px}

/* manual strip */
#manual-strip{display:flex;align-items:center;gap:10px;padding:8px 16px;border-top:1px solid var(--border);background:var(--bg2);border-radius:0 0 var(--radius) var(--radius);flex-shrink:0}
#manual-strip label{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text3);white-space:nowrap}
#manual-ip{background:var(--surface);border:1.5px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:13px;padding:5px 10px;border-radius:6px;outline:none;width:155px;transition:border-color .15s,box-shadow .15s}
#manual-ip:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(26,110,247,.12)}
#manual-ip.error{border-color:var(--red);box-shadow:0 0 0 3px rgba(220,38,38,.12)}
#manual-err{font-size:11px;color:var(--red);flex:1}
#btn-monitor{background:var(--accent);color:#fff;border:none;border-radius:6px;padding:6px 14px;font-family:var(--mono);font-size:11px;font-weight:700;cursor:pointer;letter-spacing:.5px;transition:background .15s,transform .1s}
#btn-monitor:hover{background:var(--accent2);transform:translateY(-1px)}

/* divider */
#divider{height:18px;display:flex;align-items:center;justify-content:center;gap:4px;flex-shrink:0}
#divider::before,#divider::after{content:'';height:1px;flex:1;background:var(--border)}
#divider span{font-size:9px;color:var(--text3);letter-spacing:2px;white-space:nowrap;font-weight:700;padding:0 8px}

/* traffic pane */
#bot-pane{margin:0 0 8px}
.target-chip{background:var(--green-bg);border:1px solid var(--green-b);color:var(--green);font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px;letter-spacing:.5px}
#traffic-scroll{overflow-y:auto;flex:1}
#traffic-scroll::-webkit-scrollbar{width:5px}
#traffic-scroll::-webkit-scrollbar-track{background:var(--bg)}
#traffic-scroll::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.t-row{display:grid;grid-template-columns:100px 50px 140px 68px 68px 1fr;align-items:center;padding:5px 16px;border-bottom:1px solid var(--border);transition:background .08s;animation:fadeUp .15s ease both}
@keyframes fadeUp{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:translateY(0)}}
.t-row:hover{background:var(--bg)}
.t-time{font-size:11px;color:var(--text3)}
.t-dir{font-size:10px;font-weight:700;letter-spacing:.5px;display:inline-flex;align-items:center;justify-content:center;padding:2px 6px;border-radius:4px;width:fit-content}
.t-dir.out{background:#ede9fe;color:var(--purple)}
.t-dir.in{background:var(--cyan-bg);color:var(--cyan)}
.t-peer{font-size:11px;color:var(--text2)}
.t-bytes{font-size:11px;color:var(--text3);text-align:right}
.t-detail{font-size:11px;color:var(--text3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-left:8px}
.badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;letter-spacing:.3px}
.b-HTTP{background:var(--green-bg);color:var(--green)}
.b-TLS{background:var(--purple-bg);color:var(--purple)}
.b-SSH{background:var(--orange-bg);color:var(--orange)}
.b-DNS{background:var(--yellow-bg);color:var(--yellow)}
.b-ICMP{background:var(--red-bg);color:var(--red)}
.b-TCP{background:var(--cyan-bg);color:var(--cyan)}
.b-UDP{background:#f0f4ff;color:var(--accent)}
.b-DHCP{background:var(--yellow-bg);color:var(--yellow)}
.b-FTP{background:var(--orange-bg);color:var(--orange)}
.b-SMTP{background:var(--purple-bg);color:var(--purple)}
.b-other{background:var(--bg2);color:var(--text3)}
#traffic-idle{padding:20px 16px;color:var(--text3);font-size:12px}

/* footer */
#footer{display:flex;align-items:center;gap:16px;padding:0 4px;border-top:1px solid var(--border);font-size:11px;color:var(--text3)}
.kbd{background:var(--bg2);border:1px solid var(--border2);padding:1px 6px;border-radius:4px;font-size:10px;color:var(--text2)}
.fsep{color:var(--border2)}
#pkt-total{margin-left:auto;color:var(--accent);font-weight:700}
</style>
</head>
<body>
<div id="app">

  <div id="header">
    <span class="logo">NetScan <span>// """ + NETWORK + r"""</span></span>
    <span class="tag" id="mode-tag">ARP SWEEP</span>
    <span id="ws-badge" class="disc">● CONNECTING</span>
    <div id="scan-status">
      <div class="dot scanning" id="sdot"></div>
      <span id="stext">Connecting to scanner…</span>
    </div>
  </div>

  <div class="pane" id="top-pane">
    <div class="pane-head">
      <span class="pane-title">Live Hosts — ARP Sweep Results</span>
      <span class="pane-badge" id="host-count-label">waiting…</span>
    </div>
    <div class="progress-wrap"><div class="progress-bar" id="prog-bar"></div></div>
    <div class="col-head host-cols">
      <span>#</span><span>IP Address</span><span>MAC Address</span><span>Note</span><span>Action</span>
    </div>
    <div id="host-scroll">
      <div class="empty-state" id="empty-msg">
        <span style="font-size:16px">◌</span> Waiting for scan results…
      </div>
    </div>
    <div id="manual-strip">
      <label>Manual IP</label>
      <input id="manual-ip" type="text" placeholder="10.0.0.x" maxlength="15" spellcheck="false">
      <span id="manual-err"></span>
      <button id="btn-monitor">Monitor →</button>
    </div>
  </div>

  <div id="divider"><span>LIVE TRAFFIC</span></div>

  <div class="pane" id="bot-pane">
    <div class="pane-head">
      <span class="pane-title">Packet Capture</span>
      <span class="target-chip" id="target-chip" style="display:none">─</span>
      <span class="pane-badge" id="pkt-label">no target selected</span>
    </div>
    <div class="col-head traffic-cols">
      <span>Timestamp</span><span>Dir</span><span>Peer IP</span>
      <span>Protocol</span><span style="text-align:right">Bytes</span>
      <span style="padding-left:8px">Detail</span>
    </div>
    <div id="traffic-scroll">
      <div id="traffic-idle">Select a discovered host — or enter an IP manually — to begin live packet capture.</div>
    </div>
  </div>

  <div id="footer">
    <span><span class="kbd">Click</span> or <span class="kbd">↑↓ Enter</span> select host</span>
    <span class="fsep">|</span>
    <span><span class="kbd">M</span> manual IP</span>
    <span class="fsep">|</span>
    <span><span class="kbd">Esc</span> clear target</span>
    <span id="pkt-total" style="margin-left:auto">PKT: 0</span>
  </div>
</div>

<script>
const WS_URL = 'ws://localhost:""" + str(WS_PORT) + r"""';
let ws, hosts=[], selected=-1, pktTotal=0;

function isValidIP(s){
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(s)&&s.split('.').every(n=>+n>=0&&+n<=255);
}

// ── WebSocket ──────────────────────────────────────────────────
function connect(){
  ws = new WebSocket(WS_URL);

  ws.onopen = ()=>{
    document.getElementById('ws-badge').className='ws-badge conn';
    document.getElementById('ws-badge').textContent='● LIVE';
    document.getElementById('stext').textContent='Connected — waiting for scan…';
  };

  ws.onclose = ()=>{
    document.getElementById('ws-badge').className='ws-badge disc';
    document.getElementById('ws-badge').textContent='● DISCONNECTED';
    setTimeout(connect, 2000);
  };

  ws.onmessage = e=>{
    const msg = JSON.parse(e.data);

    if(msg.type==='init'){
      hosts = msg.hosts||[];
      if(msg.scan_done) finishScan();
      else setScanningState();
      renderHosts();
      if(msg.target){ setTarget(msg.target,false); }
      // replay buffered traffic
      if(msg.traffic&&msg.traffic.length){
        msg.traffic.slice().reverse().forEach(p=>addPacketRow(p));
      }
    }

    else if(msg.type==='scan_done'){
      hosts = msg.hosts||[];
      finishScan();
      renderHosts();
    }

    else if(msg.type==='packet'){
      addPacketRow(msg);
      pktTotal++;
      document.getElementById('pkt-label').textContent=`${pktTotal} packets captured`;
      document.getElementById('pkt-total').textContent=`PKT: ${pktTotal}`;
    }

    else if(msg.type==='target_set'){
      setTarget(msg.ip, true);
    }

    else if(msg.type==='error'){
      document.getElementById('manual-err').textContent=msg.msg;
      document.getElementById('manual-ip').classList.add('error');
    }
  };
}

// ── scan state ────────────────────────────────────────────────
function setScanningState(){
  document.getElementById('sdot').className='dot scanning';
  document.getElementById('stext').textContent='ARP sweep in progress…';
  document.getElementById('prog-bar').style.width='60%';
  document.getElementById('host-count-label').textContent='scanning…';
}

function finishScan(){
  document.getElementById('sdot').className='dot live';
  document.getElementById('stext').textContent=`Scan complete — ${hosts.length} live host(s) found`;
  document.getElementById('prog-bar').style.width='100%';
  document.getElementById('host-count-label').textContent=`${hosts.length} hosts found`;
  document.getElementById('mode-tag').textContent='SCAN COMPLETE';
  document.getElementById('mode-tag').className='tag live';
  document.getElementById('empty-msg').style.display='none';
}

// ── render hosts ──────────────────────────────────────────────
function renderHosts(){
  const scroll = document.getElementById('host-scroll');
  const sy = scroll.scrollTop;
  scroll.querySelectorAll('.host-row').forEach(r=>r.remove());
  if(hosts.length) document.getElementById('empty-msg').style.display='none';

  hosts.forEach((h,i)=>{
    const row = document.createElement('div');
    row.className = 'host-row'+(i===selected?' active':'');
    row.innerHTML=`
      <span class="h-num">${String(i+1).padStart(3,'0')}</span>
      <span class="h-ip">${h.ip}</span>
      <span class="h-mac">${h.mac}</span>
      <span class="h-note">${h.note||''}</span>
      <button class="h-btn">${i===selected?'● Monitoring':'Monitor'}</button>`;
    row.querySelector('.h-btn').addEventListener('click',ev=>{ev.stopPropagation();selectHost(i);});
    row.addEventListener('click',()=>selectHost(i));
    scroll.appendChild(row);
  });
  scroll.scrollTop = sy;
}

// ── select host ───────────────────────────────────────────────
function selectHost(idx){
  selected = idx;
  renderHosts();
  if(ws&&ws.readyState===1){
    ws.send(JSON.stringify({type:'set_target', ip:hosts[idx].ip}));
  }
}

function setTarget(ip, clearLog){
  document.getElementById('target-chip').textContent=ip;
  document.getElementById('target-chip').style.display='';
  document.getElementById('pkt-label').textContent='capturing…';
  document.getElementById('traffic-idle').style.display='none';
  if(clearLog){
    pktTotal=0;
    document.getElementById('traffic-scroll').querySelectorAll('.t-row').forEach(r=>r.remove());
    document.getElementById('pkt-total').textContent='PKT: 0';
  }
}

// ── add packet row ────────────────────────────────────────────
function addPacketRow(p){
  const scroll = document.getElementById('traffic-scroll');
  const row = document.createElement('div');
  row.className='t-row';
  const bc = ['HTTP','TLS','SSH','DNS','ICMP','TCP','UDP','DHCP','FTP','SMTP'].includes(p.proto)
    ? `b-${p.proto}` : 'b-other';
  row.innerHTML=`
    <span class="t-time">${p.ts}</span>
    <span class="t-dir ${p.dir==='OUT'?'out':'in'}">${p.dir}</span>
    <span class="t-peer">${p.peer}</span>
    <span><span class="badge ${bc}">${p.proto}</span></span>
    <span class="t-bytes" style="text-align:right">${p.size}B</span>
    <span class="t-detail">${p.detail||''}</span>`;
  scroll.insertBefore(row, scroll.firstChild);
  while(scroll.querySelectorAll('.t-row').length>300)
    scroll.lastElementChild.remove();
}

// ── manual IP ─────────────────────────────────────────────────
document.getElementById('btn-monitor').addEventListener('click', doManual);
document.getElementById('manual-ip').addEventListener('keydown', e=>{
  if(e.key==='Enter') doManual();
  if(e.key==='Escape'){
    document.getElementById('manual-ip').value='';
    document.getElementById('manual-err').textContent='';
    document.getElementById('manual-ip').classList.remove('error');
  }
});

function doManual(){
  const inp=document.getElementById('manual-ip');
  const ip=inp.value.trim();
  if(!isValidIP(ip)){
    inp.classList.add('error');
    document.getElementById('manual-err').textContent=`"${ip}" — invalid IPv4`;
    inp.focus(); return;
  }
  inp.classList.remove('error');
  document.getElementById('manual-err').textContent='';
  // add to host list if not present
  if(!hosts.find(h=>h.ip===ip)){
    hosts.push({ip, mac:'──:──:──:──:──:──', note:'Manual entry'});
    selected=hosts.length-1;
  } else {
    selected=hosts.findIndex(h=>h.ip===ip);
  }
  renderHosts();
  if(ws&&ws.readyState===1)
    ws.send(JSON.stringify({type:'set_target',ip}));
  inp.value='';
}

// ── keyboard nav ──────────────────────────────────────────────
document.addEventListener('keydown',e=>{
  if(document.activeElement===document.getElementById('manual-ip')) return;
  if(e.key==='ArrowUp'){e.preventDefault();if(selected>0){selected--;renderHosts();}}
  if(e.key==='ArrowDown'){e.preventDefault();if(selected<hosts.length-1){selected++;renderHosts();}}
  if(e.key==='Enter'&&selected>=0) selectHost(selected);
  if(e.key==='m'||e.key==='M') document.getElementById('manual-ip').focus();
  if(e.key==='Escape'){
    selected=-1;
    document.getElementById('target-chip').style.display='none';
    document.getElementById('pkt-label').textContent='no target selected';
    document.getElementById('traffic-scroll').querySelectorAll('.t-row').forEach(r=>r.remove());
    document.getElementById('traffic-idle').style.display='';
    renderHosts();
  }
});

connect();
</script>
</body>
</html>"""


# ═════════════════════════════════════════════════════════════════
# HTTP Server (serves the HTML page)
# ═════════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def log_message(self, *a):
        pass   # silence access log


def run_http():
    HTTPServer(("localhost", HTTP_PORT), Handler).serve_forever()


# ═════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════
async def main():
    global _loop
    _loop = asyncio.get_running_loop()

    # root check
    if sys.platform != "win32" and os.geteuid() != 0:
        print("Root privileges required.  Run:  sudo python3 net_scanner_server.py")
        sys.exit(1)

    # HTTP server in background thread
    threading.Thread(target=run_http, daemon=True).start()
    print(f"[*] HTTP server  →  http://localhost:{HTTP_PORT}")

    # ARP scan in background thread
    threading.Thread(target=arp_scan, daemon=True).start()
    print(f"[*] ARP sweep    →  {NETWORK}")

    # Open browser after a short delay
    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{HTTP_PORT}")
    threading.Thread(target=open_browser, daemon=True).start()

    # WebSocket server
    print(f"[*] WebSocket    →  ws://localhost:{WS_PORT}")
    print(f"[*] Press Ctrl+C to stop.\n")
    async with websockets.serve(ws_handler, "localhost", WS_PORT):
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")