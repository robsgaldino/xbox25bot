# 🎮 xbox25bot — Monitor de pré-venda do Xbox Series X25 (25 anos)

Bot que checa a cada **10 minutos** as lojas oficiais **dos EUA** e dispara
alertas em múltiplos canais quando a pré-venda do **Xbox Series X25 Limited
Edition** abrir (anunciado em 07/06/2026, lançamento em novembro/2026;
pré-venda ainda sem data).

## 📺 Interface de acompanhamento

**<http://localhost:8425>** — dashboard local (roda sempre, via launchd).
Mostra o status de cada loja, os sinais detectados vs. baseline, canais de
alerta e o log. Botões para **checar agora** e **testar notificações**.

## Como funciona a detecção

Na primeira execução o bot gravou uma "baseline" de cada página (quantas vezes
frases como `pre-order`, `series x25`, `x25 limited` aparecem hoje). A cada
checagem ele compara e alerta quando:

- uma frase-sinal que era **0** aparece (ex: "x25 limited" na busca da Microsoft Store), ou
- a contagem **salta** para mais de 2× a baseline + 3 (produto surgiu na busca).

Quando dispara, re-alerta a cada checagem (máx. **5 alertas por site / 24h**).

## Lojas monitoradas (foco EUA)

| Loja | Status |
|---|---|
| Xbox.com EUA — página 25th Anniversary | ✅ ativo |
| Xbox.com EUA — página de consoles | ✅ ativo |
| Microsoft Store EUA — busca "xbox series x25" | ✅ ativo |
| Newegg EUA — busca | ✅ ativo |
| Target EUA — busca | ✅ ativo |
| Walmart EUA — busca | ✅ ativo |
| Xbox.com Brasil — 25 anos (bônus) | ✅ ativo |
| Amazon EUA | ❌ anti-bot com desafio JS — desativado |
| Best Buy / GameStop / Costco / Antonline | ❌ bloqueiam bots (403) — desativados |

Para as lojas bloqueadas, a redundância é: alerta oficial da Microsoft
(cadastre-se em <https://www.xbox.com/en-US/xbox-25th-anniversary>) + a própria
Microsoft Store, que historicamente abre a pré-venda primeiro.

## Canais de alerta

| Canal | Status | O que falta |
|---|---|---|
| 🖥️ Notificação do macOS + voz | ✅ funcionando | nada |
| 📱 Push no celular (ntfy) | ✅ funcionando | instale o app **ntfy** e assine o tópico `xbox25-robson-b8fd9d74` |
| 💬 WhatsApp → +55 48 99142-3350 | ⚙️ falta só o apikey | adicione **+34 644 71 81 99** aos contatos, mande "I allow callmebot to send me messages" no WhatsApp, cole o apikey em `config.json` → `whatsapp_callmebot` e mude `enabled` para `true` |
| 📲 SMS → +55 48 99142-3350 | ⚙️ falta conta Twilio | conta trial grátis em twilio.com; preencha SID, token e número de origem em `config.json` (seu número de destino já está lá) |
| 📧 E-mail → robson@atom6studio.com | ⚙️ falta senha de app | [senha de app do Gmail](https://myaccount.google.com/apppasswords) em `config.json` → `email` |
| ✈️ Telegram | ⚙️ opcional | bot via @BotFather, token + chat_id no config |

Depois de configurar qualquer canal: `python3 xbox25bot.py --test-notify`
(ou o botão 🧪 no dashboard).

## Comandos

```bash
python3 xbox25bot.py                 # uma checagem manual
python3 xbox25bot.py --status        # estado de cada site no terminal
python3 xbox25bot.py --baseline      # re-grava a baseline (se mudar sinais/sites)
python3 xbox25bot.py --test-notify   # testa todos os canais ativos
tail -f bot.log                      # acompanhar o log
```

## Agendamento (launchd)

| Agente | Função |
|---|---|
| `com.atom6.xbox25bot` | checagem a cada 10 min |
| `com.atom6.xbox25bot.dashboard` | dashboard em localhost:8425, sempre ativo |

```bash
launchctl bootout  gui/$UID/com.atom6.xbox25bot              # parar o bot
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.atom6.xbox25bot.plist
```

⚠️ Só roda com o Mac ligado/acordado — o push do ntfy no celular cobre você
fora de casa, e o cadastro no alerta oficial da Microsoft é a segunda rede de
segurança.

## Falsos positivos

O bot prefere alertar a mais do que perder a pré-venda. Se um site mudar o
layout e gerar alerta falso, rode `python3 xbox25bot.py --baseline` para
re-calibrar.
