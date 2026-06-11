#!/usr/bin/env python3
"""
Dashboard local do xbox25bot — http://localhost:8425

UI inspirada no Xbox 25th Anniversary (X25): vidro translúcido verde,
tiles estilo home do Xbox, imagens oficiais e animações.
"""

import json
import mimetypes
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
STATE_FILE = BASE / "state.json"
LOG_FILE = BASE / "bot.log"
BOT = BASE / "xbox25bot.py"
ASSETS = BASE / "assets"
PORT = int(os.environ.get("PORT", 8425))

CHANNEL_META = {
    "macos": ("🖥️", "Mac", "notificação + voz"),
    "ntfy": ("📱", "Push celular", "app ntfy"),
    "whatsapp_callmebot": ("💬", "WhatsApp", "+55 48 9142-3350"),
    "sms_twilio": ("📲", "SMS", "via Twilio"),
    "email": ("📧", "E-mail", "robson@atom6studio.com"),
    "telegram": ("✈️", "Telegram", "bot"),
}


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def status_payload():
    cfg = load(CONFIG_FILE, {"sites": [], "channels": {}})
    state = load(STATE_FILE, {"sites": {}})
    sites = []
    for site in cfg["sites"]:
        st = state["sites"].get(site["id"], {})
        status = "desativado" if not site.get("enabled", True) else st.get("last_status", "aguardando")
        sites.append({
            "id": site["id"],
            "name": site["name"],
            "url": site["url"],
            "enabled": site.get("enabled", True),
            "status": status,
            "last_check": st.get("last_check"),
            "baseline": st.get("baseline"),
            "last_counts": st.get("last_counts"),
            "fail_streak": st.get("fail_streak", 0),
            "alerts_24h": len([t for t in st.get("alerts", []) if time.time() - t < 86400]),
            "last_trigger": st.get("last_trigger"),
        })
    channels = []
    for key, (icon, label, sub) in CHANNEL_META.items():
        ch = cfg["channels"].get(key, {})
        channels.append({"id": key, "icon": icon, "label": label, "sub": sub,
                         "enabled": bool(ch.get("enabled"))})
    try:
        log_tail = LOG_FILE.read_text().splitlines()[-60:]
    except OSError:
        log_tail = []
    return {"generated_at": time.strftime("%d/%m/%Y %H:%M:%S"),
            "sites": sites, "channels": channels, "log": log_tail}


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>XBOX 25 — Monitor de Pré-venda</title>
<style>
  :root {
    --og:#107C10; --lime:#9bf00b; --neon:#5dde3a;
    --glass:rgba(20, 40, 22, .38); --glass2:rgba(16, 32, 18, .55);
    --stroke:rgba(155, 240, 11, .18); --stroke2:rgba(155, 240, 11, .45);
    --txt:#eaf6e8; --dim:#9fc4a0; --red:#ff4f4f; --amber:#ffb02e;
    --f-title:"Bahnschrift", "DIN Alternate", "Avenir Next Condensed", "Segoe UI", sans-serif;
    --f-body:"Segoe UI", -apple-system, system-ui, sans-serif;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  html { scroll-behavior:smooth; }
  body {
    min-height:100vh; color:var(--txt); overflow-x:hidden;
    font:15px/1.5 var(--f-body);
    background:#030803;
  }
  h1, h2, h3, .pill, .badge, .btn, .brand small, #clock, .gs {
    font-family:var(--f-title);
  }
  /* fundo: keyart + véu escuro + auroras animadas */
  .bg, .bg::after { position:fixed; inset:0; z-index:-3; }
  .bg {
    background:url('/assets/x25-wallpaper.jpg') center/cover no-repeat;
    filter:blur(26px) saturate(1.25) brightness(.7);
    transform:scale(1.15); animation:bgdrift 60s ease-in-out infinite alternate;
  }
  .bg::after { content:''; background:radial-gradient(ellipse at 50% -10%, transparent 0%, rgba(2,6,2,.88) 70%); }
  @keyframes bgdrift { from { transform:scale(1.15) translateX(-1.5%);} to { transform:scale(1.15) translateX(1.5%);} }
  .blob { position:fixed; border-radius:50%; filter:blur(90px); opacity:.5; z-index:-2; pointer-events:none; }
  .blob.a { width:46vw; height:46vw; background:#0f6e0f; top:-12vw; left:-10vw; animation:float1 26s ease-in-out infinite alternate; }
  .blob.b { width:34vw; height:34vw; background:#2ea043; bottom:-14vw; right:-8vw; animation:float2 32s ease-in-out infinite alternate; }
  .blob.c { width:20vw; height:20vw; background:#9bf00b; top:40vh; left:62vw; opacity:.13; animation:float1 22s ease-in-out infinite alternate-reverse; }
  @keyframes float1 { from { transform:translate(0,0);} to { transform:translate(7vw,5vh);} }
  @keyframes float2 { from { transform:translate(0,0);} to { transform:translate(-6vw,-6vh);} }
  /* partículas subindo */
  .dust { position:fixed; bottom:-10px; width:4px; height:4px; border-radius:50%;
          background:var(--lime); opacity:0; z-index:-1; animation:rise linear infinite; }
  @keyframes rise { 0% { opacity:0; transform:translateY(0) scale(.6);} 12% { opacity:.55;}
                    100% { opacity:0; transform:translateY(-105vh) scale(1.15);} }

  .wrap { max-width:1280px; margin:0 auto; padding:22px 28px 60px; }

  /* topbar estilo console — logo oficial X25 */
  .topbar { display:flex; align-items:center; gap:16px; padding:10px 4px 14px; }
  /* linha de vida: varredura contínua = bot online */
  .lifeline { position:relative; height:2px; margin:0 4px 22px; border-radius:2px;
              background:rgba(155,240,11,.13); overflow:hidden; }
  .lifeline::after { content:''; position:absolute; top:0; bottom:0; width:16%;
                     background:linear-gradient(90deg, transparent, rgba(155,240,11,.95), transparent);
                     box-shadow:0 0 12px rgba(155,240,11,.6);
                     animation:sweep 2.8s linear infinite; }
  @keyframes sweep { from { left:-18%; } to { left:102%; } }
  .lifeline.dead { background:rgba(255,176,46,.16); }
  .lifeline.dead::after { background:linear-gradient(90deg, transparent, rgba(255,176,46,.8), transparent);
                          box-shadow:none; animation-duration:9s; }
  .logo { height:74px; width:auto; flex:none; mix-blend-mode:screen;
          animation:logoglow 3.6s ease-in-out infinite; }
  @keyframes logoglow {
    0%, 100% { filter:brightness(1) drop-shadow(0 0 10px rgba(155,240,11,.25)); }
    50% { filter:brightness(1.18) drop-shadow(0 0 26px rgba(155,240,11,.55)); }
  }
  .brand small { display:block; font-size:12px; font-weight:400; color:var(--dim); letter-spacing:2.5px; }
  .top-right { margin-left:auto; display:flex; align-items:center; gap:18px; }
  .gs { display:flex; align-items:center; gap:7px; background:var(--glass); border:1px solid var(--stroke);
        border-radius:99px; padding:6px 14px; backdrop-filter:blur(14px); font-weight:600; font-size:13px; }
  .gs .g { width:20px; height:20px; border-radius:50%; background:var(--og); color:#fff; font-weight:800;
           display:flex; align-items:center; justify-content:center; font-size:12px; }
  #clock { font-size:20px; font-weight:300; color:#fff; letter-spacing:1px; font-variant-numeric:tabular-nums; }

  /* hero */
  .hero { position:relative; border-radius:22px; overflow:hidden; min-height:330px;
          display:flex; align-items:stretch;
          background:var(--glass); border:1px solid var(--stroke);
          backdrop-filter:blur(22px); -webkit-backdrop-filter:blur(22px);
          box-shadow:0 22px 70px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.09); }
  .hero .art { position:absolute; inset:0; z-index:0;
               background:url('/assets/x25-console.jpg') right center/cover no-repeat;
               animation:kenburns 24s ease-in-out infinite alternate; }
  @keyframes kenburns { from { transform:scale(1.02);} to { transform:scale(1.1) translateX(-1.2%);} }
  .hero .veil { position:absolute; inset:0; z-index:1;
                background:linear-gradient(95deg, rgba(3,10,4,.94) 30%, rgba(3,10,4,.55) 58%, rgba(3,10,4,.06) 100%); }
  .hero .in { position:relative; z-index:2; padding:38px 42px; max-width:600px;
              display:flex; flex-direction:column; gap:13px; justify-content:center; }
  .pill { align-self:flex-start; display:flex; align-items:center; gap:9px; font-size:12.5px; font-weight:700;
          letter-spacing:1.6px; text-transform:uppercase; padding:7px 16px; border-radius:99px;
          background:rgba(155,240,11,.1); border:1px solid var(--stroke2); color:var(--lime); }
  .pill .dot { width:9px; height:9px; border-radius:50%; background:var(--lime);
               box-shadow:0 0 10px var(--lime); animation:blink 1.8s ease-in-out infinite; }
  @keyframes blink { 50% { opacity:.25; } }
  .pill.alert { background:rgba(255,79,79,.14); border-color:rgba(255,79,79,.6); color:#ff8080; }
  .pill.alert .dot { background:var(--red); box-shadow:0 0 12px var(--red); animation:blink .6s infinite; }
  .pill.warn { background:rgba(255,176,46,.13); border-color:rgba(255,176,46,.6); color:var(--amber); }
  .pill.warn .dot { background:var(--amber); box-shadow:0 0 12px var(--amber); animation:blink .8s infinite; }
  .hero h1 { font-size:42px; line-height:1.08; font-weight:800; }
  .hero h1 span { color:transparent; background:linear-gradient(100deg,#eaffd0,var(--lime) 55%, var(--neon));
                  -webkit-background-clip:text; background-clip:text; }
  .hero p { color:var(--dim); max-width:46ch; }
  .cta { display:flex; gap:12px; margin-top:8px; flex-wrap:wrap; }
  .btn { border:0; cursor:pointer; font-weight:700; font-size:14.5px; border-radius:12px; padding:12px 22px;
         color:#04220a; background:linear-gradient(120deg, #c4f95c, var(--lime));
         box-shadow:0 8px 26px rgba(155,240,11,.3); transition:.2s; }
  .btn:hover { transform:translateY(-2px); box-shadow:0 12px 32px rgba(155,240,11,.45); }
  .btn.sec { background:rgba(255,255,255,.07); color:var(--txt); border:1px solid var(--stroke);
             backdrop-filter:blur(10px); box-shadow:none; }
  /* botão comprar: dormente até a pré-venda abrir */
  .btn.buy { background:rgba(255,255,255,.04); color:#647a67; border:1.5px dashed rgba(155,240,11,.28);
             cursor:not-allowed; box-shadow:none; letter-spacing:1px; }
  .btn.buy:hover { transform:none; box-shadow:none; }
  .btn.buy.live { cursor:pointer; color:#04220a; border:0; letter-spacing:1px;
                  background:linear-gradient(120deg, #d9ff8a, var(--lime));
                  animation:buypulse 1s ease-in-out infinite; }
  .btn.buy.live:hover { transform:translateY(-2px); }
  @keyframes buypulse { 0%,100% { box-shadow:0 0 18px rgba(155,240,11,.5);}
                        50% { box-shadow:0 0 52px rgba(155,240,11,.95);} }
  .hero .meta { font-size:12.5px; color:var(--dim); }

  /* seções e fileiras de tiles, estilo home do Xbox */
  h2.sec { font-size:19px; font-weight:700; margin:36px 4px 14px; display:flex; align-items:center; gap:10px; }
  h2.sec::after { content:''; flex:1; height:1px; background:linear-gradient(90deg, var(--stroke2), transparent); }
  .row { display:grid; gap:14px; grid-template-columns:repeat(auto-fill, minmax(225px, 1fr)); }
  .tile { position:relative; border-radius:16px; padding:18px; min-height:150px; cursor:pointer;
          display:flex; flex-direction:column; gap:8px; text-decoration:none; color:var(--txt);
          background:var(--glass2); border:1.5px solid var(--stroke);
          backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
          transition:transform .22s cubic-bezier(.2,.9,.3,1.4), border-color .2s, box-shadow .25s; }
  .tile:hover { transform:scale(1.05); border-color:var(--lime); z-index:2;
                box-shadow:0 0 0 2.5px var(--lime), 0 16px 44px rgba(0,0,0,.6), 0 0 34px rgba(155,240,11,.3); }
  .tile .fav { width:42px; height:42px; border-radius:10px; background:rgba(255,255,255,.92);
               display:flex; align-items:center; justify-content:center; }
  .tile .fav img { width:26px; height:26px; }
  .tile h3 { font-size:14.5px; line-height:1.3; font-weight:700; }
  .tile .sub { font-size:11.5px; color:var(--dim); }
  .badge { position:absolute; top:13px; right:13px; font-size:10.5px; font-weight:800; letter-spacing:.8px;
           padding:4px 10px; border-radius:99px; text-transform:uppercase; }
  .s-ok { background:rgba(155,240,11,.13); color:var(--lime); }
  .s-alerta { background:var(--red); color:#fff; animation:alarm .7s infinite; }
  .s-erro, .s-bloqueado { background:rgba(255,176,46,.15); color:var(--amber); }
  .s-desativado, .s-aguardando { background:rgba(255,255,255,.07); color:var(--dim); }
  @keyframes alarm { 50% { opacity:.45; } }
  .tile.off { opacity:.4; filter:saturate(.4); }
  .tile.hot { border-color:var(--red); box-shadow:0 0 0 2.5px var(--red), 0 0 40px rgba(255,79,79,.45);
              animation:hotpulse 1.1s ease-in-out infinite; }
  @keyframes hotpulse { 50% { box-shadow:0 0 0 2.5px var(--red), 0 0 64px rgba(255,79,79,.75);} }
  .sig { font-size:11px; color:var(--dim); margin-top:auto; line-height:1.6; }
  .sig b { color:var(--lime); }
  .sig .hot { color:var(--red); font-weight:800; }

  /* canais */
  .row.ch { grid-template-columns:repeat(auto-fill, minmax(185px, 1fr)); }
  .tile.chan { min-height:96px; flex-direction:row; align-items:center; gap:13px; cursor:default; }
  .tile.chan.on { border-color:var(--stroke2); }

  /* galeria */
  .gallery { display:grid; gap:14px; grid-template-columns:1fr; }
  .shot { border-radius:16px; overflow:hidden; border:1px solid var(--stroke); position:relative; height:420px; }
  .shot img { width:100%; height:100%; object-fit:cover; display:block; transition:transform .6s ease; }
  .shot:hover img { transform:scale(1.06); }
  .shot .cap { position:absolute; left:0; right:0; bottom:0; padding:26px 16px 12px; font-size:12.5px; font-weight:600;
               background:linear-gradient(transparent, rgba(2,8,3,.92)); }

  /* log */
  .console { border-radius:16px; background:rgba(4,12,5,.72); border:1px solid var(--stroke);
             backdrop-filter:blur(16px); padding:16px 18px; max-height:330px; overflow:auto;
             font:12px/1.75 "SF Mono", ui-monospace, Menlo, monospace; color:#a6d8a8; }
  .console .ln-alert { color:#ff8b8b; font-weight:700; }
  .console .ln-err { color:var(--amber); }
  .console::-webkit-scrollbar { width:9px; }
  .console::-webkit-scrollbar-thumb { background:rgba(155,240,11,.25); border-radius:9px; }

  #toast { position:fixed; bottom:24px; right:24px; z-index:50; display:none; align-items:center; gap:10px;
           background:rgba(10,26,12,.92); border:1px solid var(--stroke2); color:var(--txt);
           padding:13px 20px; border-radius:14px; backdrop-filter:blur(16px);
           box-shadow:0 14px 44px rgba(0,0,0,.6); animation:pop .25s ease; }
  @keyframes pop { from { transform:translateY(14px); opacity:0; } }
  .foot { margin-top:34px; text-align:center; font-size:12px; color:var(--dim); opacity:.75; }
  @media (max-width:760px) {
    .hero h1 { font-size:30px; } .hero .in { padding:26px; } .gallery { grid-template-columns:1fr; }
    #clock { display:none; }
  }
</style></head><body>
<div class="bg"></div>
<div class="blob a"></div><div class="blob b"></div><div class="blob c"></div>

<div class="wrap">
  <div class="topbar">
    <img class="logo" src="/assets/x25-logo.png?v=4" alt="Xbox 25">
    <div class="brand"><small>MONITOR DE PRÉ-VENDA · SERIES X25</small></div>
    <div class="top-right">
      <button class="btn sec" id="musicbtn" style="display:none; padding:7px 14px; font-size:12.5px"
              onclick="toggleMusic()">música: off</button>
      <div class="gs"><span class="g">G</span><span id="gs-count">0</span></div>
      <div id="clock">--:--</div>
    </div>
  </div>
  <div class="lifeline" id="lifeline" title="bot online — varredura a cada 10 min"></div>

  <div class="hero">
    <div class="art"></div><div class="veil"></div>
    <div class="in">
      <div class="pill" id="pill"><span class="dot"></span><span id="pill-txt">monitorando</span></div>
      <h1 id="headline">Caçando a pré-venda do <span>Series X25</span></h1>
      <p id="sub">Xbox Series X25 Limited Edition — translúcido verde OG, lançamento em novembro de 2026.
         O bot varre as lojas oficiais americanas a cada 10 minutos.</p>
      <div class="cta">
        <button class="btn buy" id="buybtn" onclick="buy()" title="acende quando a pré-venda abrir">COMPRAR — PRÉ-VENDA FECHADA</button>
        <button class="btn" onclick="act('check')">Checar agora</button>
        <button class="btn sec" onclick="act('test')">Testar notificações</button>
      </div>
      <div class="meta">Última atualização: <span id="ts">…</span> · tela atualiza a cada 30 s</div>
    </div>
  </div>

  <h2 class="sec">Lojas monitoradas</h2>
  <div class="row" id="sites"></div>

  <h2 class="sec">Canais de alerta</h2>
  <div class="row ch" id="channels"></div>

  <h2 class="sec">O alvo</h2>
  <div class="gallery">
    <div class="shot"><img src="/assets/x25-collection.jpg" alt="Xbox Series X25 Limited Edition"><div class="cap">Xbox Series X25 Limited Edition · Novembro 2026</div></div>
  </div>

  <h2 class="sec">Atividade do bot</h2>
  <pre class="console" id="log"></pre>

  <div class="foot">xbox25bot · rodando neste Mac via launchd · checagem a cada 10 min · WhatsApp + push + voz quando abrir</div>
</div>
<div id="toast"></div>

<script>
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const STATUS_LABEL = { ok:'monitorando', ALERTA:'ALERTA', erro:'erro', bloqueado:'bloqueado',
                       desativado:'desativado', aguardando:'aguardando' };
let alertUrl = null;

// partículas
for (let i = 0; i < 22; i++) {
  const d = document.createElement('div'); d.className = 'dust';
  d.style.left = Math.random() * 100 + 'vw';
  d.style.animationDuration = 9 + Math.random() * 16 + 's';
  d.style.animationDelay = -Math.random() * 20 + 's';
  d.style.width = d.style.height = (2 + Math.random() * 3.5) + 'px';
  document.body.appendChild(d);
}

function tickClock() {
  const n = new Date();
  let h = n.getHours(); const ap = h >= 12 ? 'pm' : 'am'; h = h % 12 || 12;
  document.getElementById('clock').textContent =
    String(h).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0') + ' ' + ap;
}
tickClock(); setInterval(tickClock, 1000);

function sigHtml(s) {
  if (!s.baseline) return '';
  const cur = s.last_counts || {};
  const parts = Object.entries(s.baseline).map(([k, b]) => {
    const n = cur[k] ?? '–';
    const hot = typeof n === 'number' && (b === 0 ? n > 0 : n > b * 2 + 3);
    return hot ? `<span class="hot">${esc(k)}: ${n}</span>` : `${esc(k)}: <b>${n}</b>`;
  });
  return `<div class="sig">${parts.join(' · ')}</div>`;
}

async function refresh() {
  let d; try { d = await (await fetch('/api/status')).json(); } catch { return; }
  document.getElementById('ts').textContent = d.generated_at;

  const sites = d.sites.filter(s => s.enabled);
  const alertSite = sites.find(s => s.status === 'ALERTA');
  const anyAlert = !!alertSite;
  alertUrl = alertSite ? alertSite.url : null;

  // watchdog: a checagem mais recente entre os sites ativos
  const newest = Math.max(0, ...sites.filter(s => s.last_check)
    .map(s => new Date(s.last_check.replace(' ', 'T')).getTime()));
  const ageMin = newest ? Math.round((Date.now() - newest) / 60000) : null;
  const stale = ageMin === null || ageMin > 15;

  const pill = document.getElementById('pill');
  pill.className = 'pill' + (anyAlert ? ' alert' : stale ? ' warn' : '');
  document.getElementById('pill-txt').textContent =
    anyAlert ? 'PRÉ-VENDA DETECTADA'
    : stale ? `bot sem rodar há ${ageMin ?? '?'} min — verifique o launchd`
    : `última varredura há ${ageMin} min`;
  document.getElementById('headline').innerHTML = anyAlert
    ? 'CORRE! A pré-venda do <span>Series X25</span> pode ter aberto!'
    : 'Caçando a pré-venda do <span>Series X25</span>';

  document.getElementById('lifeline').className = 'lifeline' + (stale ? ' dead' : '');

  const buy = document.getElementById('buybtn');
  buy.className = 'btn buy' + (anyAlert ? ' live' : '');
  buy.textContent = anyAlert ? 'COMPRAR AGORA' : 'COMPRAR — PRÉ-VENDA FECHADA';

  document.getElementById('gs-count').textContent =
    d.log.filter(l => l.includes(': ok') || l.includes('ALERTA')).length * 113 + 21337;

  document.getElementById('sites').innerHTML = sites.map(s => {
    const host = new URL(s.url).hostname;
    const cls = 'tile' + (s.status === 'ALERTA' ? ' hot' : '');
    return `<a class="${cls}" href="${esc(s.url)}" target="_blank" title="abrir loja">
      <span class="badge s-${esc(s.status.toLowerCase())}">${esc(STATUS_LABEL[s.status] || s.status)}</span>
      <span class="fav"><img src="https://www.google.com/s2/favicons?domain=${esc(host)}&sz=64"
            onerror="this.parentNode.style.display='none'"></span>
      <h3>${esc(s.name)}</h3>
      <span class="sub">${esc(host)} · ${esc(s.last_check || 'sem checagem')}</span>
      ${s.last_trigger ? `<div class="sig"><span class="hot">${esc(s.last_trigger)}</span></div>` : ''}
      ${sigHtml(s)}
      ${s.fail_streak ? `<div class="sig">${s.fail_streak} falhas seguidas</div>` : ''}
    </a>`;
  }).join('');

  document.getElementById('channels').innerHTML = d.channels.filter(c => c.enabled).map(c => `
    <div class="tile chan on">
      <div><h3>${esc(c.label)}</h3><span class="sub">${esc(c.sub)}</span></div>
      <span class="badge s-ok">ativo</span>
    </div>`).join('');

  const logEl = document.getElementById('log');
  logEl.innerHTML = d.log.map(l => {
    const cls = /ALERTA/.test(l) ? 'ln-alert' : /ERRO|FALHOU|suspeita/.test(l) ? 'ln-err' : '';
    return `<span class="${cls}">${esc(l)}</span>`;
  }).join('\n');
  logEl.scrollTop = logEl.scrollHeight;

  document.title = (anyAlert ? 'PRÉ-VENDA! — ' : '') + 'XBOX 25 — Monitor de Pré-venda';
}

function buy() {
  if (alertUrl) window.open(alertUrl, '_blank');
}

async function act(kind) {
  toast(kind === 'check' ? 'Checando todas as lojas…' : 'Disparando notificações de teste…');
  try { await fetch('/api/' + kind, { method:'POST' }); } catch {}
  setTimeout(() => { refresh(); toast('Feito!'); }, kind === 'check' ? 25000 : 9000);
}

/* ---------- áudio: blip de hover (estilo dashboard Xbox) + música tema ---------- */
let actx = null, unlocked = false;

function blip() {
  if (!unlocked) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const t = actx.currentTime;
    const o = actx.createOscillator(), g = actx.createGain();
    o.type = 'sine';
    o.frequency.setValueAtTime(760, t);
    o.frequency.exponentialRampToValueAtTime(1240, t + .05);
    g.gain.setValueAtTime(.0001, t);
    g.gain.exponentialRampToValueAtTime(.12, t + .015);
    g.gain.exponentialRampToValueAtTime(.0001, t + .16);
    o.connect(g); g.connect(actx.destination);
    o.start(t); o.stop(t + .18);
  } catch {}
}

let lastHover = null;
document.addEventListener('pointerover', e => {
  const el = e.target.closest('a.tile, .btn');
  if (el && el !== lastHover) { lastHover = el; blip(); }
  if (!el) lastHover = null;
});

// música tema: toca /assets/halo3.mp3 em loop, se o arquivo existir
const music = new Audio('/assets/halo3.mp3');
music.loop = true; music.volume = .25;
let musicAvailable = false;
let musicWanted = localStorage.getItem('x25music') !== 'off';

fetch('/assets/halo3.mp3', { method:'HEAD' }).then(r => {
  musicAvailable = r.ok && (r.headers.get('content-type') || '').includes('audio');
  if (musicAvailable) updateMusicBtn();
}).catch(() => {});

function updateMusicBtn() {
  const b = document.getElementById('musicbtn');
  b.style.display = 'inline-block';
  b.textContent = 'música: ' + (musicWanted && !music.paused ? 'on' : musicWanted ? 'on (clique na página)' : 'off');
}
function toggleMusic() {
  musicWanted = !musicWanted;
  localStorage.setItem('x25music', musicWanted ? 'on' : 'off');
  if (musicWanted) music.play().catch(() => {}); else music.pause();
  updateMusicBtn();
}
// navegadores exigem 1 gesto antes de tocar áudio — o 1º clique/toque libera tudo
function unlock() {
  unlocked = true;
  actx = actx || new (window.AudioContext || window.webkitAudioContext)();
  if (actx.state === 'suspended') actx.resume();
  if (musicAvailable && musicWanted && music.paused) {
    music.play().then(updateMusicBtn).catch(() => {});
  }
}
document.addEventListener('pointerdown', unlock);
document.addEventListener('keydown', unlock);
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'flex';
  clearTimeout(t._h); t._h = setTimeout(() => t.style.display = 'none', 5000);
}
refresh(); setInterval(refresh, 30000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8", cache=False):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/status":
            self._send(200, json.dumps(status_payload(), ensure_ascii=False),
                       "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE)
        elif self.path.startswith("/assets/"):
            name = Path(self.path.split("?", 1)[0]).name  # sem traversal nem query string
            f = ASSETS / name
            if f.is_file():
                ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
                self._send(200, f.read_bytes(), ctype, cache=True)
            else:
                self._send(404, "not found", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def do_HEAD(self):
        if self.path.startswith("/assets/"):
            name = Path(self.path.split("?", 1)[0]).name
            f = ASSETS / name
            if f.is_file():
                self.send_response(200)
                self.send_header("Content-Type",
                                 mimetypes.guess_type(name)[0] or "application/octet-stream")
            else:
                self.send_response(404)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/check":
            subprocess.Popen([sys.executable, str(BOT)])
            self._send(200, '{"ok":true}', "application/json")
        elif self.path == "/api/test":
            subprocess.Popen([sys.executable, str(BOT), "--test-notify"])
            self._send(200, '{"ok":true}', "application/json")
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args):
        pass  # sem ruído no launchd.log


if __name__ == "__main__":
    print(f"Dashboard em http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
