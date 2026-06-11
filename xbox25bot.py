#!/usr/bin/env python3
"""
xbox25bot — monitora distribuidores oficiais do Xbox e avisa quando a
pré-venda do Xbox Series X25 Limited Edition (25th Anniversary) abrir.

Uso:
  python3 xbox25bot.py              # roda uma checagem (modo normal, usado pelo launchd)
  python3 xbox25bot.py --baseline   # re-grava a baseline de todos os sites (sem alertar)
  python3 xbox25bot.py --test-notify# dispara um alerta de teste em todos os canais ativos
  python3 xbox25bot.py --status     # mostra estado de cada site monitorado

Detecção: para cada site, conta ocorrências de frases-sinal (ex: "pré-venda",
"series x25"). Na primeira execução grava a baseline. Depois, alerta quando:
  - um sinal que era 0 na baseline aparece, ou
  - a contagem de um sinal supera (2x baseline + 3) — produto surgiu na busca.
"""

import json
import os
import re
import ssl
import sys
import time
import smtplib
import subprocess
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_FILE = Path(os.environ.get("XBOX25_CONFIG", BASE / "config.json"))
STATE_FILE = BASE / "state.json"
LOG_FILE = BASE / "bot.log"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MAX_ALERTS_PER_SITE_24H = 5  # repete o alerta (difícil de ignorar) mas não vira spam


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def curl(url, timeout=25, data=None, headers=None, method=None):
    """HTTP via curl do sistema (usa a cadeia de certificados do macOS,
    evitando problemas de SSL do Python instalado via python.org)."""
    cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout),
           "-A", UA, "--fail-with-body"]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if data is not None:
        cmd += ["--data-binary", data if isinstance(data, str) else data.decode()]
    if method:
        cmd += ["-X", method]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    if proc.returncode != 0:
        raise RuntimeError(f"curl rc={proc.returncode}: {proc.stderr.decode(errors='ignore')[:200]}")
    return proc.stdout.decode("utf-8", errors="ignore")


def fetch(url, timeout=25):
    return curl(url, timeout=timeout, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    })


def count_signals(html, signals):
    text = html.lower()
    return {sig: len(re.findall(re.escape(sig.lower()), text)) for sig in signals}


# ---------------------------------------------------------------- notificações

def notify_macos(title, message, cfg):
    try:
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], timeout=15, capture_output=True)
        if cfg.get("speak"):
            subprocess.run(["say", "-v", "Luciana", cfg.get("speak_text",
                           "Atenção! A pré-venda do Xbox 25 anos pode ter aberto!")],
                           timeout=30, capture_output=True)
        return True
    except Exception as e:
        log(f"  macos FALHOU: {e}")
        return False


def notify_ntfy(title, message, url, cfg):
    try:
        curl(f"https://ntfy.sh/{cfg['topic']}", data=message, method="POST", headers={
            "Title": title.encode("ascii", "ignore").decode(),
            "Priority": "urgent",
            "Tags": "video_game,rotating_light",
            **({"Click": url} if url else {}),
        })
        return True
    except Exception as e:
        log(f"  ntfy FALHOU: {e}")
        return False


def notify_email(title, message, cfg):
    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = Header(title, "utf-8")
        msg["From"] = cfg["from"]
        msg["To"] = cfg["to"]
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587), timeout=30) as s:
                s.starttls(context=ctx)
                s.login(cfg["smtp_user"], cfg["smtp_password"])
                s.sendmail(cfg["from"], [cfg["to"]], msg.as_string())
        except ssl.SSLCertVerificationError:
            # Python do python.org sem certificados instalados — melhor avisar
            # sem verificação do que perder o alerta da pré-venda.
            ctx = ssl._create_unverified_context()
            with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587), timeout=30) as s:
                s.starttls(context=ctx)
                s.login(cfg["smtp_user"], cfg["smtp_password"])
                s.sendmail(cfg["from"], [cfg["to"]], msg.as_string())
        return True
    except Exception as e:
        log(f"  email FALHOU: {e}")
        return False


def notify_whatsapp_callmebot(title, message, cfg):
    # https://www.callmebot.com/blog/free-api-whatsapp-messages/
    try:
        params = urllib.parse.urlencode({
            "phone": cfg["phone"],
            "text": f"{title}\n{message}",
            "apikey": cfg["apikey"],
        })
        body = curl(f"https://api.callmebot.com/whatsapp.php?{params}", timeout=30)
        # A API responde 2xx mesmo em erro — o veredito vem no corpo da página.
        low = body.lower()
        if "invalid" in low or "error" in low:
            snippet = re.sub(r"<[^>]+>", " ", body)
            snippet = re.sub(r"\s+", " ", snippet).strip()[:200]
            raise RuntimeError(f"API recusou: {snippet}")
        return True
    except Exception as e:
        log(f"  whatsapp FALHOU: {e}")
        return False


def notify_sms_twilio(title, message, cfg):
    try:
        import base64
        body = urllib.parse.urlencode({
            "From": cfg["from_number"],
            "To": cfg["to_number"],
            "Body": f"{title} — {message}"[:1500],
        })
        auth = base64.b64encode(f"{cfg['account_sid']}:{cfg['auth_token']}".encode()).decode()
        curl(f"https://api.twilio.com/2010-04-01/Accounts/{cfg['account_sid']}/Messages.json",
             data=body, timeout=30,
             headers={"Authorization": f"Basic {auth}",
                      "Content-Type": "application/x-www-form-urlencoded"})
        return True
    except Exception as e:
        log(f"  sms FALHOU: {e}")
        return False


def notify_telegram(title, message, url, cfg):
    try:
        text = f"🚨 *{title}*\n{message}" + (f"\n{url}" if url else "")
        body = urllib.parse.urlencode({
            "chat_id": cfg["chat_id"], "text": text, "parse_mode": "Markdown"})
        curl(f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage",
             data=body, timeout=30,
             headers={"Content-Type": "application/x-www-form-urlencoded"})
        return True
    except Exception as e:
        log(f"  telegram FALHOU: {e}")
        return False


def send_all(title, message, url, channels):
    sent = []
    if channels.get("macos", {}).get("enabled"):
        if notify_macos(title, message, channels["macos"]):
            sent.append("macos")
    if channels.get("ntfy", {}).get("enabled"):
        if notify_ntfy(title, message, url, channels["ntfy"]):
            sent.append("ntfy")
    if channels.get("email", {}).get("enabled"):
        if notify_email(title, f"{message}\n\nLink: {url}" if url else message, channels["email"]):
            sent.append("email")
    if channels.get("whatsapp_callmebot", {}).get("enabled"):
        if notify_whatsapp_callmebot(title, f"{message}\n{url or ''}", channels["whatsapp_callmebot"]):
            sent.append("whatsapp")
    if channels.get("sms_twilio", {}).get("enabled"):
        if notify_sms_twilio(title, message, channels["sms_twilio"]):
            sent.append("sms")
    if channels.get("telegram", {}).get("enabled"):
        if notify_telegram(title, message, url, channels["telegram"]):
            sent.append("telegram")
    return sent


# ---------------------------------------------------------------- checagem

def check_site(site, state, channels, baseline_only=False):
    sid = site["id"]
    st = state["sites"].setdefault(sid, {"baseline": None, "alerts": [], "fail_streak": 0})
    st["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        html = fetch(site["url"])
    except Exception as e:
        st["fail_streak"] = st.get("fail_streak", 0) + 1
        st["last_status"] = "erro"
        log(f"{sid}: ERRO ao buscar ({e}) [falhas seguidas: {st['fail_streak']}]")
        return

    if len(html) < site.get("min_bytes", 5000):
        st["fail_streak"] = st.get("fail_streak", 0) + 1
        st["last_status"] = "bloqueado"
        log(f"{sid}: resposta suspeita ({len(html)} bytes, possível bloqueio anti-bot) "
            f"[falhas seguidas: {st['fail_streak']}]")
        return

    st["fail_streak"] = 0
    counts = count_signals(html, site["signals"])
    st["last_counts"] = counts
    st["last_status"] = "ok"

    if st["baseline"] is None or baseline_only:
        st["baseline"] = counts
        st["baseline_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        log(f"{sid}: baseline gravada {counts}")
        return

    triggered = []
    for sig, n in counts.items():
        base = st["baseline"].get(sig, 0)
        if base == 0 and n > 0:
            triggered.append(f'"{sig}" apareceu ({n}x, antes 0)')
        elif base > 0 and n > base * 2 + 3:
            triggered.append(f'"{sig}" saltou de {base}x para {n}x')

    if not triggered:
        log(f"{sid}: ok, sem novidade {counts}")
        return

    st["last_status"] = "ALERTA"
    st["last_trigger"] = "; ".join(triggered)

    now = time.time()
    st["alerts"] = [t for t in st.get("alerts", []) if now - t < 86400]
    if len(st["alerts"]) >= MAX_ALERTS_PER_SITE_24H:
        log(f"{sid}: SINAL ATIVO mas limite de alertas/24h atingido — {triggered}")
        return

    st["alerts"].append(now)
    title = f"🚨 XBOX X25: possível pré-venda — {site['name']}"
    message = (f"Sinais detectados em {site['name']}: " + "; ".join(triggered) +
               ". Abra o link e confira AGORA!")
    log(f"{sid}: ALERTA! {triggered}")
    sent = send_all(title, message, site["url"], channels)
    log(f"{sid}: notificado via {sent or 'NENHUM CANAL (verifique config)'}")


def apply_env_overrides(cfg):
    """Em CI (GitHub Actions) as credenciais vêm de Secrets, não do config."""
    ch = cfg["channels"]
    if os.environ.get("NTFY_TOPIC"):
        ch["ntfy"] = {"enabled": True, "topic": os.environ["NTFY_TOPIC"]}
    if os.environ.get("CALLMEBOT_PHONE") and os.environ.get("CALLMEBOT_APIKEY"):
        ch["whatsapp_callmebot"] = {"enabled": True,
                                    "phone": os.environ["CALLMEBOT_PHONE"],
                                    "apikey": os.environ["CALLMEBOT_APIKEY"]}
    if sys.platform != "darwin":
        ch.setdefault("macos", {})["enabled"] = False


def main():
    cfg = load_json(CONFIG_FILE, None)
    if cfg is None:
        log("config.json não encontrado ou inválido — abortando")
        sys.exit(1)
    apply_env_overrides(cfg)
    state = load_json(STATE_FILE, {"sites": {}})

    if "--test-notify" in sys.argv:
        sent = send_all("🧪 Teste do xbox25bot",
                        "Se você recebeu isto, este canal está funcionando. "
                        "O bot está monitorando a pré-venda do Xbox Series X25.",
                        "https://www.xbox.com/pt-BR/xbox-25th-anniversary",
                        cfg["channels"])
        print(f"Canais que enviaram com sucesso: {sent}")
        return

    if "--status" in sys.argv:
        for site in cfg["sites"]:
            st = state["sites"].get(site["id"], {})
            print(f"{site['id']:>14}: baseline={st.get('baseline_at', '—')} "
                  f"falhas_seguidas={st.get('fail_streak', 0)} "
                  f"alertas_24h={len(st.get('alerts', []))}")
        return

    baseline_only = "--baseline" in sys.argv
    for site in cfg["sites"]:
        if not site.get("enabled", True):
            continue
        check_site(site, state, cfg["channels"], baseline_only)
        time.sleep(1)

    heartbeat(cfg, state)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def heartbeat(cfg, state):
    """Prova de vida 1x/dia (entre 8h e 22h) no ntfy e WhatsApp — sem voz no Mac."""
    state["runs_since_hb"] = state.get("runs_since_hb", 0) + 1
    if time.time() - state.get("last_heartbeat", 0) < 23 * 3600:
        return
    if not 8 <= time.localtime().tm_hour <= 22:
        return
    enabled = [s for s in cfg["sites"] if s.get("enabled", True)]
    ok = sum(1 for s in enabled
             if state["sites"].get(s["id"], {}).get("last_status") == "ok")
    src = "☁️ nuvem (GitHub)" if os.environ.get("GITHUB_ACTIONS") else "💻 Mac"
    msg = (f"💚 Bot vivo [{src}]: {state['runs_since_hb']} varreduras desde o último resumo, "
           f"{ok}/{len(enabled)} lojas respondendo agora. "
           f"Nenhum sinal de pré-venda do X25 ainda — sigo de olho a cada 10 min.")
    sent = []
    ch = cfg["channels"]
    if ch.get("ntfy", {}).get("enabled") and notify_ntfy("xbox25bot — resumo diário", msg, None, ch["ntfy"]):
        sent.append("ntfy")
    if ch.get("whatsapp_callmebot", {}).get("enabled") and \
            notify_whatsapp_callmebot("xbox25bot — resumo diário", msg, ch["whatsapp_callmebot"]):
        sent.append("whatsapp")
    if sent:
        state["last_heartbeat"] = time.time()
        state["runs_since_hb"] = 0
        log(f"heartbeat diário enviado via {sent}")


if __name__ == "__main__":
    main()
