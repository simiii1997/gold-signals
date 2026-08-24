"""
Gold-Scalping SIGNAL-Bot (kein Auto-Trading!)
================================================

Prüft einmalig, ob gerade ein Kauf-/Verkaufssignal vorliegt
(EMA-Kreuzung auf M1-Kerzen) und schickt dir bei einem Treffer
eine Telegram-Nachricht. Die Order bestätigst/platzierst du danach
SELBST in der capital.com App.

Läuft NICHT dauerhaft -> wird per GitHub Actions alle paar Minuten
automatisch neu gestartet (siehe .github/workflows/signal-check.yml).
Kein eigener Server nötig, kostenlos.

Benötigte GitHub Secrets (siehe SETUP.md):
    CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_EPIC
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import requests

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
EPIC = os.environ.get("CAPITAL_EPIC", "GOLD")
EMA_PERIOD = int(os.environ.get("EMA_PERIOD", "20"))
CANDLE_RESOLUTION = "MINUTE"


def login():
    url = f"{BASE_URL}/session"
    headers = {"X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"], "Content-Type": "application/json"}
    payload = {
        "identifier": os.environ["CAPITAL_IDENTIFIER"],
        "password": os.environ["CAPITAL_PASSWORD"],
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.headers["CST"], resp.headers["X-SECURITY-TOKEN"]


def get_closes(cst, token):
    url = f"{BASE_URL}/prices/{EPIC}"
    headers = {
        "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"],
        "CST": cst,
        "X-SECURITY-TOKEN": token,
    }
    params = {"resolution": CANDLE_RESOLUTION, "max": EMA_PERIOD + 10}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    prices = resp.json()["prices"]
    closes = []
    for candle in prices:
        c = candle["closePrice"]
        closes.append((c["bid"] + c["ask"]) / 2)
    return closes


def decide_signal(closes, ema_period):
    if len(closes) < ema_period + 2:
        return None
    k = 2 / (ema_period + 1)
    ema = sum(closes[:ema_period]) / ema_period
    ema_series = [ema]
    for price in closes[ema_period:]:
        ema = price * k + ema * (1 - k)
        ema_series.append(ema)

    prev_close, last_close = closes[-2], closes[-1]
    prev_ema, last_ema = ema_series[-2], ema_series[-1]

    if prev_close < prev_ema and last_close > last_ema:
        return "BUY", last_close
    if prev_close > prev_ema and last_close < last_ema:
        return "SELL", last_close
    return None


def send_telegram(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
    resp.raise_for_status()


def main():
    cst, token = login()
    closes = get_closes(cst, token)
    signal = decide_signal(closes, EMA_PERIOD)

    if signal:
        direction, price = signal
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"{emoji} {direction}-Signal auf {EPIC}\n"
            f"Kurs: {price:.2f}\n"
            f"EMA{EMA_PERIOD}-Kreuzung erkannt.\n"
            f"Bitte manuell in der capital.com App prüfen und ggf. Order platzieren."
        )
        send_telegram(msg)
        print(f"Signal gesendet: {direction} @ {price:.2f}")
    else:
        print("Kein Signal.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)

