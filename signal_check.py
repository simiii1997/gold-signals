"""
Gold-Swing-Signal-Bot (kein Auto-Trading!) - M15, EMA20/EMA50
==================================================================

STRATEGIE (Swing/kurzfristiger Trend, passend zum 5-Minuten-Check):
- M15-Kerzen (15-Minuten-Kerzen) statt M1
- EMA20 (schnell) kreuzt EMA50 (langsam)
- BUY: EMA20 kreuzt von unten nach oben ueber EMA50 (Trendwechsel nach oben)
- SELL: EMA20 kreuzt von oben nach unten unter EMA50 (Trendwechsel nach unten)

WARUM DIESER ZEITRAHMEN JETZT SINN ERGIBT:
Bei M1-Kerzen ist eine 5-Minuten-Pruefverzoegerung fatal, weil die
gesamte Bewegung oft nur 1-3 Minuten dauert. Bei M15-Kerzen dauert eine
einzelne Kerze bereits 15 Minuten - eine Verzoegerung von 5 Minuten beim
Erkennen macht hier nur einen kleinen Teil der Bewegung aus, nicht die
ganze. Ein EMA20/50-Crossover auf M15 zeigt typischerweise einen
Trend, der sich ueber mehrere Stunden entwickelt - genug Zeit, um nach
der Benachrichtigung noch sinnvoll zu reagieren.

WICHTIG: Auch diese Strategie ist nicht "sicher" oder garantiert
profitabel - EMA-Crossover-Systeme haben in Seitwaertsphasen weiterhin
viele Fehlsignale. Sie ist lediglich technisch sinnvoller mit der
aktuellen 5-Minuten-Pruefarchitektur vereinbar als ein M1-Ansatz.

Benötigte GitHub Secrets (gleich geblieben):
    CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_EPIC
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import requests

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
EPIC = os.environ.get("CAPITAL_EPIC", "GOLD")

FAST_EMA_PERIOD = int(os.environ.get("EMA_FAST", "20"))
SLOW_EMA_PERIOD = int(os.environ.get("EMA_SLOW", "50"))

CANDLE_RESOLUTION = "MINUTE_15"  # M15 statt M1
CANDLE_COUNT = SLOW_EMA_PERIOD + 15


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
    params = {"resolution": CANDLE_RESOLUTION, "max": CANDLE_COUNT}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    prices = resp.json()["prices"]
    closes = []
    for candle in prices:
        c = candle["closePrice"]
        closes.append((c["bid"] + c["ask"]) / 2)
    return closes


def ema_series(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    series = [ema]
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
        series.append(ema)
    return series


def decide_signal(closes):
    fast = ema_series(closes, FAST_EMA_PERIOD)
    slow = ema_series(closes, SLOW_EMA_PERIOD)
    if not fast or not slow:
        return None

    min_len = min(len(fast), len(slow))
    if min_len < 2:
        return None
    fast = fast[-min_len:]
    slow = slow[-min_len:]

    prev_fast, last_fast = fast[-2], fast[-1]
    prev_slow, last_slow = slow[-2], slow[-1]

    crossed_up = prev_fast < prev_slow and last_fast > last_slow
    crossed_down = prev_fast > prev_slow and last_fast < last_slow

    if crossed_up:
        return "BUY", last_fast, last_slow
    if crossed_down:
        return "SELL", last_fast, last_slow
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
    signal = decide_signal(closes)

    if signal:
        direction, fast_val, slow_val = signal
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"{emoji} {direction}-Swing-Signal auf {EPIC} (M15)\n"
            f"EMA{FAST_EMA_PERIOD}: {fast_val:.2f} | EMA{SLOW_EMA_PERIOD}: {slow_val:.2f}\n"
            f"Trendwechsel auf 15-Minuten-Basis erkannt.\n"
            f"Bitte manuell in der capital.com App prüfen und ggf. Order platzieren."
        )
        send_telegram(msg)
        print(f"Signal gesendet: {direction} (EMA{FAST_EMA_PERIOD}: {fast_val:.2f}, "
              f"EMA{SLOW_EMA_PERIOD}: {slow_val:.2f})")
    else:
        print("Kein Signal.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
