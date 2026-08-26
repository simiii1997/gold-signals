"""
Gold-Scalping SIGNAL-Bot (kein Auto-Trading!) - v2
=====================================================

VERBESSERUNG gegenueber v1:
- M5-Kerzen statt M1 (weniger Rauschen/Fehlsignale)
- Zusaetzlicher EMA50-Trendfilter: ein BUY-Signal wird nur akzeptiert,
  wenn der Kurs UEBER dem EMA50 liegt (Aufwaertstrend), ein SELL-Signal
  nur, wenn der Kurs UNTER dem EMA50 liegt (Abwaertstrend). Das reduziert
  Signale gegen den uebergeordneten Trend.

Prüft, ob gerade ein Kauf-/Verkaufssignal vorliegt (EMA20-Kreuzung auf
M5-Kerzen, bestaetigt durch EMA50-Trendfilter) und schickt bei einem
Treffer eine Telegram-Nachricht. Die Order bestätigst/platzierst du
danach SELBST in der capital.com App.

Benötigte GitHub Secrets (unveraendert):
    CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_EPIC
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import requests

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
EPIC = os.environ.get("CAPITAL_EPIC", "GOLD")

FAST_EMA_PERIOD = int(os.environ.get("EMA_PERIOD", "20"))
SLOW_EMA_PERIOD = int(os.environ.get("SLOW_EMA_PERIOD", "50"))
CANDLE_RESOLUTION = "MINUTE_5"   # M5-Kerzen statt M1
# genug Kerzen fuer den langsameren EMA plus Puffer
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
    """Gibt die komplette EMA-Reihe zurueck (gleiche Laenge wie moeglich)."""
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
    """
    Regel:
    - Fast-EMA (z.B. EMA20) kreuzt von unten nach oben -> moegliches BUY
    - Fast-EMA kreuzt von oben nach unten -> moegliches SELL
    - Bestaetigung durch Slow-EMA (z.B. EMA50) als Trendfilter:
        BUY nur, wenn letzter Schlusskurs > Slow-EMA (Aufwaertstrend)
        SELL nur, wenn letzter Schlusskurs < Slow-EMA (Abwaertstrend)
    """
    if len(closes) < SLOW_EMA_PERIOD + 2:
        return None

    fast_series = ema_series(closes, FAST_EMA_PERIOD)
    slow_series = ema_series(closes, SLOW_EMA_PERIOD)
    if not fast_series or not slow_series:
        return None

    # Serien auf gleiche Laenge bringen (am Ende ausrichten)
    min_len = min(len(fast_series), len(slow_series), len(closes))
    fast_series = fast_series[-min_len:]
    slow_series = slow_series[-min_len:]
    closes_aligned = closes[-min_len:]

    prev_close, last_close = closes_aligned[-2], closes_aligned[-1]
    prev_fast, last_fast = fast_series[-2], fast_series[-1]
    last_slow = slow_series[-1]

    crossed_up = prev_close < prev_fast and last_close > last_fast
    crossed_down = prev_close > prev_fast and last_close < last_fast

    if crossed_up and last_close > last_slow:
        return "BUY", last_close, last_slow
    if crossed_down and last_close < last_slow:
        return "SELL", last_close, last_slow
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
        direction, price, slow_ema = signal
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"{emoji} {direction}-Signal auf {EPIC} (M5)\n"
            f"Kurs: {price:.2f}\n"
            f"EMA{FAST_EMA_PERIOD}-Kreuzung, bestaetigt durch EMA{SLOW_EMA_PERIOD}-Trend "
            f"({slow_ema:.2f})\n"
            f"Bitte manuell in der capital.com App pruefen und ggf. Order platzieren."
        )
        send_telegram(msg)
        print(f"Signal gesendet: {direction} @ {price:.2f} (Trend-EMA: {slow_ema:.2f})")
    else:
        print("Kein Signal.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
