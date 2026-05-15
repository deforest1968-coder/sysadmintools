#!/usr/bin/env python3
"""
NetKit - Network Toolkit Bridge
Run:  python netkit.py
Stop: Ctrl+C
Requires: Python 3.6+, no external packages
"""

import http.server
import json
import socket
import ssl
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError

PORT = 8765

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NetKit</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'JetBrains Mono',monospace;background:radial-gradient(ellipse at 20% 50%, #1a0505 0%, #0a0a0f 50%, #000 100%);color:#cdd5e0;min-height:100vh;padding:20px}
.term{max-width:1500px;margin:0 auto;border-radius:10px;overflow:hidden;border:1px solid #2a2f3a;display:flex;flex-direction:column;height:calc(100vh - 40px)}
.titlebar{background:#181c24;padding:10px 16px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #2a2f3a;flex-shrink:0}
.dot{width:12px;height:12px;border-radius:50%}
.dot.r{background:#ff5f57}.dot.y{background:#febc2e}.dot.g{background:#28c840}
.tl{margin-left:8px;font-size:12px;color:#6b7585;letter-spacing:.05em;flex:1}
.pill{font-size:11px;padding:2px 10px;border-radius:4px;border:1px solid;cursor:pointer;font-family:inherit;background:none}
.pill.off{color:#e06c75;border-color:rgba(224,108,117,.3)}
.pill.on{color:#5cb85c;border-color:rgba(92,184,92,.3)}
.pill.mid{color:#e5c07b;border-color:rgba(229,192,123,.3)}
.body-cols{display:flex;flex:1;overflow:hidden}
.left-col{display:flex;flex-direction:column;flex:0 0 680px;border-right:1px solid #2a2f3a;overflow:hidden;background:#15181f}
.right-col{display:flex;flex-direction:column;flex:1;overflow:hidden;background:#11141a}
.banner{padding:10px 20px 12px;border-bottom:1px solid #2a2f3a;background:#15181f;flex-shrink:0}
.ascii{color:#61afef;font-size:10px;line-height:1.4;white-space:pre;opacity:.7}
.hint{color:#5a6272;font-size:12px;margin-top:6px}
.params{padding:10px 18px;background:#15181f;border-bottom:1px solid #2a2f3a;display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0}
.pg{display:flex;align-items:center;gap:6px}
.pl{font-size:11px;color:#5a6272;white-space:nowrap}
input{background:#1c2028;border:1px solid #2a2f3a;color:#cdd5e0;font-family:'JetBrains Mono',monospace;font-size:12px;padding:4px 8px;border-radius:4px;outline:none;transition:border-color .15s}
input:focus{border-color:#61afef}
.prompt-bar{padding:10px 18px;background:#1a1e27;border-bottom:1px solid #2a2f3a;display:none;align-items:center;gap:10px;flex-shrink:0}
.prompt-bar.visible{display:flex}
.prompt-label{font-size:12px;color:#e5c07b;white-space:nowrap}
.prompt-input{background:#1c2028;border:1px solid #61afef;color:#cdd5e0;font-family:'JetBrains Mono',monospace;font-size:13px;padding:5px 10px;border-radius:4px;outline:none;flex:1}
.menu-wrap{flex:1;overflow-y:auto;background:#13161c}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:8px}
.item{padding:12px 16px;cursor:pointer;border:1px solid #252a35;border-radius:6px;transition:all .15s;background:#1a1e28}
.item:hover{background:#1e2330;border-color:#3a4155;transform:translateY(-1px);box-shadow:0 3px 10px rgba(0,0,0,.4)}
.item.active{background:#1e2840;border-color:#61afef;box-shadow:0 0 0 1px rgba(97,175,239,.2),0 3px 12px rgba(97,175,239,.1)}
.ik{font-size:11px;color:#d19a66;margin-bottom:4px}
.ik b{background:#1c2028;border:1px solid #2a2f3a;border-radius:3px;padding:1px 6px;color:#abb2bf;font-weight:400;letter-spacing:.04em}
.it{font-size:14px;color:#dde3ec;font-weight:500;margin-bottom:3px;letter-spacing:.01em}
.id{font-size:12px;color:#5a6272;line-height:1.4}
.sep{cursor:default;background:transparent;border:none!important;border-radius:0!important;box-shadow:none!important;grid-column:1/-1;padding:6px 4px 2px;transform:none!important}
.abar{padding:8px 16px;border-top:1px solid #2a2f3a;display:flex;gap:8px;align-items:center;background:#181c24;flex-shrink:0}
.sl{font-size:11px;color:#5a6272;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button{font-family:'JetBrains Mono',monospace;font-size:12px;padding:5px 14px;border-radius:4px;cursor:pointer;border:1px solid;transition:all .15s;background:none}
.gbtn{color:#5cb85c;border-color:rgba(92,184,92,.35)}
.gbtn:hover{background:rgba(92,184,92,.1)}
.gbtn:disabled{opacity:.3;cursor:not-allowed}
.bbtn{color:#61afef;border-color:rgba(97,175,239,.3)}
.bbtn:hover{background:rgba(97,175,239,.08)}
.oh{padding:8px 20px;border-bottom:1px solid #2a2f3a;display:flex;align-items:center;gap:8px;background:#15181f;flex-shrink:0}
.ol{font-size:11px;color:#5a6272}
.oc{font-size:11px;color:#61afef;flex:1}
pre{padding:16px 20px;font-size:12.5px;line-height:1.9;white-space:pre-wrap;word-break:break-all;flex:1;overflow-y:auto;font-family:'JetBrains Mono',monospace;color:#b8c0cc}
.g{color:#5cb85c}.b{color:#61afef}.a{color:#e5c07b}.r{color:#e06c75}.m{color:#4b5362}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{display:inline-block;width:10px;height:10px;border:1.5px solid #333;border-top-color:#61afef;border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes blink{50%{opacity:0}}
.blink{animation:blink 1s step-end infinite}
</style>
</head>
<body>
<div class="term">
  <div class="titlebar">
    <div class="dot r"></div><div class="dot y"></div><div class="dot g"></div>
    <span class="tl">NetKit &mdash; Network Toolkit</span>
    <button class="pill off" id="pill" onclick="ping()">&#9679; disconnected</button>
  </div>
  <div class="body-cols">
    <div class="left-col">
      <div class="banner">
        <div class="ascii">  \u2588\u2588\u2588\u2557   \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2557  \u2588\u2588\u2557\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557
  \u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2551 \u2588\u2588\u2554\u255d\u2588\u2588\u2551\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d
  \u2588\u2588\u2554\u2588\u2588\u2557 \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2557     \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2554\u255d \u2588\u2588\u2551   \u2588\u2588\u2551   
  \u2588\u2588\u2551\u255a\u2588\u2588\u2557\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u255d     \u2588\u2588\u2551   \u2588\u2588\u2554\u2550\u2588\u2588\u2557 \u2588\u2588\u2551   \u2588\u2588\u2551   
  \u2588\u2588\u2551 \u255a\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557   \u2588\u2588\u2551   \u2588\u2588\u2551  \u2588\u2588\u2557\u2588\u2588\u2551   \u2588\u2588\u2551   </div>
        <div class="hint" id="hint"># Connecting to bridge...</div>
      </div>
      <div class="params">
        <div class="pg"><span class="pl">Target</span><input id="target" value="10.0.0.1" style="width:120px"></div>
        <div class="pg"><span class="pl">Subnet</span><input id="subnet" value="10.0.0" style="width:90px"></div>
        <div class="pg"><span class="pl">Domain</span><input id="domain" value="example.com" style="width:120px"></div>
        <div class="pg"><span class="pl">Ports</span><input id="ports" value="21,22,23,25,53,80,443,3389,8080" style="width:190px"></div>
        <div class="pg"><span class="pl">End</span><input id="sweep_end" value="254" style="width:45px"></div>
      </div>
      <div class="prompt-bar" id="prompt-bar">
        <span class="prompt-label" id="prompt-label">&#8594; Target</span>
        <input class="prompt-input" id="prompt-input" placeholder="domain or IP address" value="10.0.0.1">
      </div>
      <div class="menu-wrap">
        <div class="grid" id="menu"></div>
      </div>
      <div class="abar">
        <span class="sl" id="sel">select a tool</span>
        <button class="bbtn" onclick="copyOut()">copy</button>
        <button class="gbtn" id="rbtn" onclick="run()" disabled>&#9654; run</button>
      </div>
    </div>
    <div class="right-col">
      <div class="oh"><span class="ol">OUTPUT //</span><span class="oc" id="ocmd">idle</span></div>
      <pre id="out"><span class="m"># Select a tool and click Run.</span><span class="blink b"> \u2588</span></pre>
    </div>
  </div>
</div>
<script>
const tools = [
  {k:"--",t:"-- REMOTE / NETWORK --",  d:"uses target host or subnet fields",        fn:"_sep",            p:[]},
  {k:"01",t:"Ping Sweep",               d:"ICMP + TCP probe every host on subnet",    fn:"ping_sweep",      p:["subnet","sweep_end"]},
  {k:"02",t:"Host Scan",                d:"Sweep subnet, port scan all live hosts",   fn:"host_scan",       p:["subnet","ports","sweep_end"]},
  {k:"03",t:"DNS Recon",                d:"A/AAAA/MX/NS/TXT/SOA + reverse PTR",      fn:"dns_recon",       p:["domain"]},
  {k:"04",t:"Whois / GeoIP",            d:"Country, ASN, ISP, VPN/proxy detection",  fn:"geoip",           p:["target"]},
  {k:"05",t:"Reverse DNS Sweep",        d:"PTR lookup for every IP in subnet",        fn:"rdns_sweep",      p:["subnet","sweep_end"]},
  {k:"06",t:"SSL Certificate",          d:"Cert chain, expiry, SANs, issuer",         fn:"ssl_cert",        p:["target"]},
  {k:"07",t:"HTTP Headers",             d:"Response headers + security header audit", fn:"http_headers",    p:["target"]},
  {k:"--",t:"-- LOCAL MACHINE --",      d:"runs on this host only",                   fn:"_sep",            p:[]},
  {k:"08",t:"ARP Table",                d:"Local ARP cache + MAC entries",            fn:"arp_table",       p:[]},
  {k:"09",t:"Listening Ports",          d:"Ports this machine is listening on",       fn:"open_ports",      p:[]},
  {k:"10",t:"Active Connections",       d:"Established TCP connections + remote IPs", fn:"active_conns",    p:[]},
  {k:"11",t:"Interface Info",           d:"IP, MAC, gateway, DNS per adapter",        fn:"iface_info",      p:[]},
  {k:"12",t:"Route Table",              d:"Routing table with metrics",               fn:"route_table",     p:[]},
  {k:"13",t:"DNS Cache",                d:"OS resolver cache",                        fn:"dns_cache",       p:[]},
  {k:"14",t:"Hosts File",               d:"Contents of local hosts file",             fn:"hosts_file",      p:[]},
  {k:"15",t:"Firewall Rules",           d:"Active inbound/outbound firewall rules",   fn:"firewall_rules",  p:[]},
  {k:"16",t:"Wi-Fi Networks",           d:"Nearby SSIDs, signal, channel, BSSID",     fn:"wifi_scan",       p:[]},
  {k:"17",t:"Wi-Fi Details",            d:"Current connection full radio stats",       fn:"wifi_detail",     p:[]},
  {k:"18",t:"Wi-Fi History",            d:"All saved/previously joined networks",      fn:"wifi_history",    p:[]},
];
let sel=null, connected=false;

function buildMenu(){
  const m=document.getElementById('menu');
  tools.forEach((t,i)=>{
    const el=document.createElement('div');
    if(t.fn==='_sep'){
      el.className='item sep';
      el.innerHTML='<div style="font-size:10px;color:#d19a66;letter-spacing:.12em;text-transform:uppercase;display:flex;align-items:center;gap:8px"><span style="flex:1;height:1px;background:linear-gradient(90deg,#3a2a14,transparent)"></span>'+t.t+'<span style="flex:1;height:1px;background:linear-gradient(270deg,#3a2a14,transparent)"></span></div>';
      m.appendChild(el); return;
    }
    el.className='item';
    el.innerHTML='<div class="ik"><b>'+t.k+'</b></div><div class="it">'+t.t+'</div><div class="id">'+t.d+'</div>';
    el.onclick=()=>{
      document.querySelectorAll('.item').forEach(x=>x.classList.remove('active'));
      el.classList.add('active'); sel=i;
      document.getElementById('sel').textContent='['+t.k+'] '+t.t;
      document.getElementById('ocmd').textContent=t.fn;
      document.getElementById('rbtn').disabled=!connected;
      document.getElementById('out').innerHTML='<span class="m"># Ready: '+t.fn+'</span><span class="blink b"> \u2588</span>';
      const pb=document.getElementById('prompt-bar');
      const pl=document.getElementById('prompt-label');
      const pi=document.getElementById('prompt-input');
      if(t.p.includes('target')&&!t.p.includes('subnet')){
        pb.classList.add('visible');
        if(t.fn==='geoip'){pl.textContent='\u2192 IP address'; pi.placeholder='IP or leave blank for auto';}
        else if(t.fn==='ssl_cert'){pl.textContent='\u2192 Hostname'; pi.placeholder='e.g. google.com or google.com:8443';}
        else if(t.fn==='http_headers'){pl.textContent='\u2192 URL / Host'; pi.placeholder='e.g. example.com or https://example.com';}
        else{pl.textContent='\u2192 Target'; pi.placeholder='domain or IP address';}
        pi.focus();
      } else { pb.classList.remove('visible'); }
    };
    m.appendChild(el);
  });
}

function v(id){return document.getElementById(id).value.trim();}

async function ping(){
  const pill=document.getElementById('pill');
  pill.className='pill mid'; pill.textContent='\u25cf connecting...';
  try{
    const r=await fetch('/ping',{signal:AbortSignal.timeout(2000)});
    if(r.ok){
      connected=true; pill.className='pill on'; pill.textContent='\u25cf connected';
      document.getElementById('hint').innerHTML='# Bridge online at localhost:'+location.port+' \u2014 select a tool and click Run';
      if(sel!==null) document.getElementById('rbtn').disabled=false;
    } else throw 0;
  } catch{
    connected=false; pill.className='pill off'; pill.textContent='\u25cf disconnected';
    document.getElementById('hint').innerHTML='# Bridge offline \u2014 is netkit.py running?';
    document.getElementById('rbtn').disabled=true;
  }
}

async function run(){
  if(sel===null||!connected) return;
  const t=tools[sel];
  const out=document.getElementById('out');
  const btn=document.getElementById('rbtn');
  btn.disabled=true; btn.innerHTML='<span class="spin"></span>running';
  out.innerHTML='<span class="a">[*] Running '+t.fn+'...</span>\\n';
  const pb=document.getElementById('prompt-bar');
  const effectiveTarget=pb.classList.contains('visible')?document.getElementById('prompt-input').value.trim():v('target');
  try{
    const r=await fetch('/run',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fn:t.fn,target:effectiveTarget,subnet:v('subnet'),
                           domain:v('domain'),ports:v('ports'),sweep_end:v('sweep_end')}),
      signal:AbortSignal.timeout(120000)
    });
    const txt=await r.text();
    const colored=txt
      .replace(/\\bOPEN\\b/g,'<span class="g">OPEN</span>')
      .replace(/\\bclosed\\b/g,'<span class="m">closed</span>')
      .replace(/\\[ERROR\\]/g,'<span class="r">[ERROR]</span>')
      .replace(/\\[OK\\]/g,'<span class="g">[OK]</span>')
      .replace(/\\[MISSING\\]/g,'<span class="r">[MISSING]</span>')
      .replace(/\\[PRESENT\\]/g,'<span class="g">[PRESENT]</span>');
    out.innerHTML='<span class="g">[+] '+t.fn+' complete</span>\\n\\n'+colored;
  } catch(e){
    out.innerHTML='<span class="r">[!] '+(e.message||'Connection lost')+'</span>';
  }
  btn.disabled=false; btn.innerHTML='&#9654; run';
}

function copyOut(){
  navigator.clipboard.writeText(document.getElementById('out').innerText);
}

buildMenu(); ping(); setInterval(ping,8000);
</script>
</body>
</html>"""


# ── Tools ─────────────────────────────────────────────────────────

def ping_sweep(subnet, sweep_end=254):
    parts = subnet.strip().split(".")
    if len(parts) == 4:
        subnet = ".".join(parts[:3])
    try:
        end = int(sweep_end)
    except Exception:
        end = 254

    def probe(i):
        ip = "{}.{}".format(subnet, i)
        for port in (80, 443, 22, 445, 3389):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    s.close()
                    return ip
                s.close()
            except Exception:
                pass
        try:
            cmd = ["ping", "-n", "1", "-w", "500", ip] if sys.platform == "win32" else ["ping", "-c", "1", "-W", "1", ip]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if "TTL=" in r.stdout or "ttl=" in r.stdout or "bytes from" in r.stdout:
                return ip
        except Exception:
            pass
        return None

    results = []
    with ThreadPoolExecutor(max_workers=100) as ex:
        for ip in [f.result() for f in as_completed([ex.submit(probe, i) for i in range(1, end+1)])]:
            if ip:
                results.append(ip)

    if not results:
        return "No live hosts found in {}.1-{}\n\nTip: hosts blocking both ICMP and common ports will be missed.".format(subnet, end)
    results.sort(key=lambda x: list(map(int, x.split("."))))
    lines = ["{:<20} {}".format("IP Address", "Status"), "─" * 30]
    lines += ["{:<20} OPEN".format(ip) for ip in results]
    lines.append("\n{} host(s) found".format(len(results)))
    return "\n".join(lines)


def port_scan(target, ports_str):
    try:
        ports = [int(p.strip()) for p in ports_str.split(",") if p.strip()]
    except Exception:
        return "[ERROR] Invalid port list"
    try:
        resolved = socket.gethostbyname(target.strip())
    except Exception:
        return "[ERROR] Could not resolve: {}".format(target)

    def probe(port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            if s.connect_ex((resolved, port)) == 0:
                banner = ""
                try:
                    s.settimeout(0.5)
                    s.send(b"HEAD / HTTP/1.0\r\nHost: " + target.strip().encode() + b"\r\n\r\n")
                    banner = s.recv(256).decode(errors="ignore").split("\r\n")[0][:60].strip()
                except Exception:
                    pass
                s.close()
                return (port, "OPEN", banner)
            s.close()
            return (port, "closed", "")
        except Exception:
            return (port, "error", "")

    results = []
    with ThreadPoolExecutor(max_workers=50) as ex:
        for r in [f.result() for f in as_completed([ex.submit(probe, p) for p in ports])]:
            results.append(r)
    results.sort(key=lambda x: x[0])
    lines = ["Scanning: {} ({})".format(target, resolved), "{:<8} {:<10} {}".format("PORT","STATE","BANNER"), "─"*60]
    for port, state, banner in results:
        lines.append("{:<8} {:<10} {}".format(port, state, banner))
    open_count = sum(1 for _, s, _ in results if s == "OPEN")
    lines.append("\n{} open / {} scanned".format(open_count, len(ports)))
    return "\n".join(lines)


def host_scan(subnet, ports_str, sweep_end=254):
    live_output = ping_sweep(subnet, sweep_end)
    ips = [l.split()[0] for l in live_output.splitlines() if "OPEN" in l]
    if not ips:
        return "No live hosts found to scan."
    out = ["Found {} host(s). Scanning ports...\n".format(len(ips))]
    for ip in ips:
        out.append("\n{}\n  {}\n{}".format("─"*40, ip, "─"*40))
        out.append(port_scan(ip, ports_str))
    return "\n".join(out)


def dns_recon(domain):
    lines = []
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
        try:
            if sys.platform == "win32":
                r = subprocess.run(["nslookup", "-type="+rtype, domain], capture_output=True, text=True, timeout=5)
                out = r.stdout
            else:
                r = subprocess.run(["dig", "+short", rtype, domain], capture_output=True, text=True, timeout=5)
                out = r.stdout.strip()
            lines.append("  [{}]".format(rtype))
            for l in out.strip().splitlines():
                if l.strip():
                    lines.append("    {}".format(l.strip()))
            if not any(l.strip() for l in out.strip().splitlines()):
                lines.append("    (no record)")
        except Exception as e:
            lines.append("  [{}] error: {}".format(rtype, e))
    return "\n".join(lines)


def geoip(target):
    target = target.strip()
    try:
        import ipaddress
        try:
            addr = ipaddress.ip_address(target)
            if addr.is_private or addr.is_loopback or not target:
                target = urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
        except Exception:
            pass
        url = "http://ip-api.com/json/{}?fields=status,query,country,regionName,city,isp,org,as,lat,lon,mobile,proxy,hosting".format(target)
        data = json.loads(urlopen(url, timeout=5).read())
        if data.get("status") != "success":
            return "[ERROR] Lookup failed for {}".format(target)
        return "\n".join([
            "  IP        : {}".format(data.get("query")),
            "  Country   : {}".format(data.get("country")),
            "  Region    : {}".format(data.get("regionName")),
            "  City      : {}".format(data.get("city")),
            "  ISP       : {}".format(data.get("isp")),
            "  Org       : {}".format(data.get("org")),
            "  ASN       : {}".format(data.get("as")),
            "  Lat/Lon   : {}, {}".format(data.get("lat"), data.get("lon")),
            "  Mobile    : {}".format(data.get("mobile")),
            "  Proxy/VPN : {}".format(data.get("proxy")),
            "  Datacenter: {}".format(data.get("hosting")),
        ])
    except Exception as e:
        return "[ERROR] {}".format(e)


def rdns_sweep(subnet, sweep_end=254):
    parts = subnet.strip().split(".")
    if len(parts) == 4:
        subnet = ".".join(parts[:3])
    try:
        end = int(sweep_end)
    except Exception:
        end = 254

    def lookup(i):
        ip = "{}.{}".format(subnet, i)
        try:
            return (ip, socket.gethostbyaddr(ip)[0])
        except Exception:
            return (ip, None)

    results = []
    with ThreadPoolExecutor(max_workers=100) as ex:
        for r in [f.result() for f in as_completed([ex.submit(lookup, i) for i in range(1, end+1)])]:
            results.append(r)

    results.sort(key=lambda x: list(map(int, x[0].split("."))))
    found = [(ip, h) for ip, h in results if h]
    if not found:
        return "No PTR records found for {}.1-{}".format(subnet, end)
    lines = ["{:<20} {}".format("IP", "Hostname"), "─"*60]
    lines += ["{:<20} {}".format(ip, host) for ip, host in found]
    lines.append("\n{} PTR record(s) of {} probed".format(len(found), end))
    return "\n".join(lines)


def ssl_cert(target):
    import datetime
    target = target.strip()
    host = target.split(":")[0]
    port = int(target.split(":")[1]) if ":" in target else 443
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ctx.wrap_socket(socket.create_connection((host, port), timeout=5), server_hostname=host) as s:
            cert = s.getpeercert()
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer  = dict(x[0] for x in cert.get("issuer", []))
        sans    = [v for _, v in cert.get("subjectAltName", [])]
        not_after = cert.get("notAfter", "")
        try:
            exp = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            days_left = (exp - datetime.datetime.utcnow()).days
            expiry_note = "  ({} days remaining)".format(days_left) if days_left > 0 else "  *** EXPIRED {} days ago ***".format(abs(days_left))
        except Exception:
            expiry_note = ""
        lines = [
            "Target      : {}:{}".format(host, port), "",
            "=== Subject ===",
            "  CN        : {}".format(subject.get("commonName", "n/a")),
            "  Org       : {}".format(subject.get("organizationName", "n/a")),
            "  Country   : {}".format(subject.get("countryName", "n/a")),
            "",
            "=== Issuer ===",
            "  CN        : {}".format(issuer.get("commonName", "n/a")),
            "  Org       : {}".format(issuer.get("organizationName", "n/a")),
            "",
            "=== Validity ===",
            "  Not Before: {}".format(cert.get("notBefore", "")),
            "  Not After : {}{}".format(not_after, expiry_note),
            "",
            "=== Subject Alt Names ({}) ===".format(len(sans)),
        ]
        lines += ["  {}".format(s) for s in sans[:40]]
        if len(sans) > 40:
            lines.append("  ... and {} more".format(len(sans)-40))
        return "\n".join(lines)
    except Exception as e:
        return "[ERROR] {}".format(e)


def http_headers(target):
    target = target.strip()
    if not target.startswith("http"):
        url = None
        for scheme in ("https", "http"):
            try:
                test_url = "{}://{}".format(scheme, target)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = Request(test_url, headers={"User-Agent": "NetKit/1.0"})
                urlopen(req, timeout=5, context=ctx)
                url = test_url
                break
            except Exception:
                continue
        if not url:
            return "[ERROR] Could not connect to {}".format(target)
    else:
        url = target

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": "NetKit/1.0"})
        resp = urlopen(req, timeout=8, context=ctx)
        headers = dict(resp.headers)
        status  = resp.status
    except Exception as e:
        return "[ERROR] {}".format(e)

    sec_headers = {
        "strict-transport-security", "content-security-policy",
        "x-frame-options", "x-content-type-options", "x-xss-protection",
        "referrer-policy", "permissions-policy",
    }
    lines = ["URL    : {}".format(url), "Status : {}".format(status), "", "=== All Headers ==="]
    for k, v in sorted(headers.items()):
        lines.append("  {:<40} {}".format(k, v))
    lines.append("\n=== Security Header Audit ===")
    header_keys_lower = {k.lower() for k in headers}
    for h in sorted(sec_headers):
        if h in header_keys_lower:
            val = next(v for k, v in headers.items() if k.lower() == h)
            lines.append("  [PRESENT] {}: {}".format(h, val[:80]))
        else:
            lines.append("  [MISSING] {}".format(h))
    return "\n".join(lines)


def arp_table():
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        return r.stdout or "(empty)"
    except Exception as e:
        return "[ERROR] {}".format(e)


def open_ports():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
            lines = [l for l in r.stdout.splitlines() if "LISTENING" in l]
            return "\n".join(["Listening ports:\n"] + lines) if lines else "(none)"
        else:
            r = subprocess.run(["ss", "-tulnp"], capture_output=True, text=True, timeout=10)
            return r.stdout or "(no output)"
    except Exception as e:
        return "[ERROR] {}".format(e)


def active_conns():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
            lines = [l for l in r.stdout.splitlines() if "ESTABLISHED" in l]
            return "Established connections:\n\n" + "\n".join(lines) if lines else "(no established connections)"
        else:
            r = subprocess.run(["ss", "-tnp", "state", "established"], capture_output=True, text=True, timeout=10)
            return r.stdout or "(no established connections)"
    except Exception as e:
        return "[ERROR] {}".format(e)


def iface_info():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(["ip", "addr"], capture_output=True, text=True, timeout=5)
            r2 = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=5)
            return r.stdout + "\n" + r2.stdout
        return r.stdout
    except Exception as e:
        return "[ERROR] {}".format(e)


def route_table():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["route", "print"], capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=5)
        return r.stdout or "(empty)"
    except Exception as e:
        return "[ERROR] {}".format(e)


def dns_cache():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["ipconfig", "/displaydns"], capture_output=True, text=True, timeout=10)
            return r.stdout or "(DNS cache empty)"
        else:
            for cmd in [["resolvectl", "statistics"], ["systemd-resolve", "--statistics"]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        return r.stdout
                except FileNotFoundError:
                    continue
            return "[ERROR] No DNS cache tool found"
    except Exception as e:
        return "[ERROR] {}".format(e)


def hosts_file():
    import os
    path = r"C:\Windows\System32\drivers\etc\hosts" if sys.platform == "win32" else "/etc/hosts"
    try:
        with open(path, "r") as f:
            raw = f.read()
        active = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        lines = ["Hosts file: {}".format(path), "{} active entries".format(len(active)), "─"*50, ""]
        lines += active if active else ["(no active entries)"]
        return "\n".join(lines)
    except PermissionError:
        return "[ERROR] Permission denied — run as Administrator"
    except Exception as e:
        return "[ERROR] {}".format(e)


def firewall_rules():
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "status=enabled"],
                capture_output=True, text=True, timeout=20
            )
            return r.stdout or "(no output)"
        elif sys.platform == "darwin":
            r = subprocess.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--listapps"],
                               capture_output=True, text=True, timeout=10)
            return r.stdout or r.stderr or "(no output)"
        else:
            for cmd in [["iptables", "-L", "-n", "-v"], ["nft", "list", "ruleset"]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if r.returncode == 0:
                        return r.stdout
                except FileNotFoundError:
                    continue
            return "[ERROR] No firewall tool found"
    except Exception as e:
        return "[ERROR] {}".format(e)


def wifi_scan():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True, timeout=10)
            return r.stdout or "(no Wi-Fi output)"
        elif sys.platform == "darwin":
            r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"], capture_output=True, text=True, timeout=10)
            return r.stdout or r.stderr or "(no output)"
        else:
            for cmd in [["nmcli", "dev", "wifi", "list"], ["iwlist", "scan"]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if r.returncode == 0:
                        return r.stdout
                except FileNotFoundError:
                    continue
            return "[ERROR] No Wi-Fi scan tool found"
    except Exception as e:
        return "[ERROR] {}".format(e)


def wifi_detail():
    try:
        if sys.platform == "win32":
            r1 = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
            r2 = subprocess.run(["netsh", "wlan", "show", "drivers"], capture_output=True, text=True, timeout=10)
            return "=== INTERFACE ===\n" + r1.stdout + "\n=== DRIVER ===\n" + r2.stdout
        elif sys.platform == "darwin":
            r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"], capture_output=True, text=True, timeout=10)
            return r.stdout or r.stderr
        else:
            out = []
            for cmd in [["iwconfig"], ["iw", "dev"]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        out.append(r.stdout)
                        break
                except FileNotFoundError:
                    continue
            return "\n".join(out) or "[ERROR] No Wi-Fi info available"
    except Exception as e:
        return "[ERROR] {}".format(e)


def wifi_history():
    try:
        if sys.platform == "win32":
            r = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=10)
            profiles = [l.split(":")[1].strip() for l in r.stdout.splitlines() if "All User Profile" in l]
            if not profiles:
                return r.stdout or "(no saved profiles)"
            lines = ["{:<4} {:<40} {}".format("#", "SSID", "Security"), "─"*60]
            for i, name in enumerate(profiles, 1):
                try:
                    r2 = subprocess.run(["netsh", "wlan", "show", "profile", "name={}".format(name)], capture_output=True, text=True, timeout=5)
                    auth = next((l.split(":")[1].strip() for l in r2.stdout.splitlines() if "Authentication" in l and ":" in l), "")
                    lines.append("  {:<4} {:<40} {}".format(i, name, auth))
                except Exception:
                    lines.append("  {:<4} {}".format(i, name))
            lines.append("\n{} saved network(s)".format(len(profiles)))
            return "\n".join(lines)
        else:
            import os
            out = []
            for path in ["/etc/NetworkManager/system-connections", "/etc/wpa_supplicant"]:
                try:
                    files = os.listdir(path)
                    out.append("\n=== {} ===".format(path))
                    out += ["  {}".format(f) for f in sorted(files)]
                except Exception:
                    pass
            return "\n".join(out) if out else "[ERROR] No Wi-Fi history found"
    except Exception as e:
        return "[ERROR] {}".format(e)


# ── Dispatch ──────────────────────────────────────────────────────

DISPATCH = {
    "ping_sweep":    lambda p: ping_sweep(p.get("subnet","10.0.0"), p.get("sweep_end",254)),
    "host_scan":     lambda p: host_scan(p.get("subnet","10.0.0"), p.get("ports","22,80,443"), p.get("sweep_end",254)),
    "dns_recon":     lambda p: dns_recon(p.get("domain","example.com")),
    "geoip":         lambda p: geoip(p.get("target","auto")),
    "rdns_sweep":    lambda p: rdns_sweep(p.get("subnet","10.0.0"), p.get("sweep_end",254)),
    "ssl_cert":      lambda p: ssl_cert(p.get("target","example.com")),
    "http_headers":  lambda p: http_headers(p.get("target","example.com")),
    "arp_table":     lambda p: arp_table(),
    "open_ports":    lambda p: open_ports(),
    "active_conns":  lambda p: active_conns(),
    "iface_info":    lambda p: iface_info(),
    "route_table":   lambda p: route_table(),
    "dns_cache":     lambda p: dns_cache(),
    "hosts_file":    lambda p: hosts_file(),
    "firewall_rules":lambda p: firewall_rules(),
    "wifi_scan":     lambda p: wifi_scan(),
    "wifi_detail":   lambda p: wifi_detail(),
    "wifi_history":  lambda p: wifi_history(),
}


# ── HTTP handler ──────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("  -> {} {}".format(args[0], args[1]))

    def send(self, code, ctype, body):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(b))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, "text/html; charset=utf-8", HTML)
        elif self.path == "/ping":
            self.send(200, "text/plain", "pong")
        elif self.path == "/favicon.ico":
            self.send(204, "text/plain", "")
        else:
            self.send(404, "text/plain", "[ERROR] Not found")

    def do_POST(self):
        if self.path != "/run":
            self.send(404, "text/plain", "[ERROR] Unknown endpoint")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            params = json.loads(body)
            fn = params.get("fn", "")
            if fn not in DISPATCH:
                self.send(400, "text/plain", "[ERROR] Unknown function: {}".format(fn))
                return
            result = DISPATCH[fn](params)
            self.send(200, "text/plain; charset=utf-8", result)
        except Exception as e:
            self.send(500, "text/plain", "[ERROR] {}".format(e))


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("localhost", PORT), Handler)
    print()
    print("  [OK] NetKit running at http://localhost:{}".format(PORT))
    print("       Python {}".format(sys.version.split()[0]))
    print("       Ctrl+C to stop")
    print()

    def open_browser():
        time.sleep(0.6)
        webbrowser.open("http://localhost:{}".format(PORT))

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [!] Stopped.")
        server.shutdown()
