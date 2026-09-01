"""
Gold-Scalping SIGNAL-Bot (kein Auto-Trading!) - Bollinger + RSI
==================================================================

STRATEGIE (Mean-Reversion, typisch fuers Scalping):
- Bollinger Baender (Periode 20, 2 Standardabweichungen) auf M1-Kerzen
- RSI (Periode 14) als Bestaetigungsfilter

BUY-Signal:
    - vorherige Kerze schloss UNTER dem unteren Bollinger-Band
    - aktuelle Kerze schliesst wieder DARUEBER (Rueckkehr)
    - RSI der vorherigen Kerze lag unter 30 (ueberverkauft)

SELL-Signal:
    - vorherige Kerze schloss UEBER dem oberen Bollinger-Band
    - aktuelle Kerze schliesst wieder DARUNTER (Rueckkehr)
    - RSI der vorherigen Kerze lag ueber 70 (ueberkauft)

Diese Logik reagiert auf kurzfristige Kursuebertreibungen und liefert
dadurch deutlich mehr Signale als eine EMA-Trendkreuzung - dafuer sind
einzelne Signale nicht zwingend "sicherer", nur haeufiger. Mean-Reversion
funktioniert tendenziell besser in Seitwaertsphasen und schlechter in
starken, klaren Trends (dort kann der Kurs laenger ausserhalb der
Baender bleiben, als man erwartet).

Benötigte GitHub Secrets (gleich geblieben):
    CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_EPIC
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import math
import requests

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
EPIC = os.environ.get("CAPITAL_EPIC", "GOLD")

BB_PERIOD = int(os.environ.get("BB_PERIOD", "20"))
BB_STD_DEV = float(os.environ.get("BB_STD_DEV", "2.0"))
RSI_PERIOD = int(os.environ.get("RSI_PERIOD", "14"))
RSI_OVERSOLD = float(os.environ.get("RSI_OVERSOLD", "30"))
RSI_OVERBOUGHT = float(os.environ.get("RSI_OVERBOUGHT", "70"))

CANDLE_RESOLUTION = "MINUTE"  # M1 - fuer schnellere Scalping-Signale
CANDLE_COUNT = max(BB_PERIOD, RSI_PERIOD) + 20


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


def bollinger_bands(closes, period, std_dev_mult):
    """Gibt Listen (mid, upper, lower) zurueck, ausgerichtet aufs Ende von closes."""
    if len(closes) < period:
        return None, None, None
    mids, uppers, lowers = [], [], []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std_dev = math.sqrt(variance)
        mids.append(mean)
        uppers.append(mean + std_dev_mult * std_dev)
        lowers.append(mean - std_dev_mult * std_dev)
    return mids, uppers, lowers


def rsi_series(closes, period):
    """Klassischer RSI (Wilder-Glaettung), ausgerichtet aufs Ende von closes."""
    if len(closes) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsis = []

    def calc_rsi(ag, al):
        if al == 0:
            return 100.0
        rs = ag / al
        return 100 - (100 / (1 + rs))

    rsis.append(calc_rsi(avg_gain, avg_loss))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsis.append(calc_rsi(avg_gain, avg_loss))

    return rsis


def decide_signal(closes):
    mids, uppers, lowers = bollinger_bands(closes, BB_PERIOD, BB_STD_DEV)
    rsis = rsi_series(closes, RSI_PERIOD)
    if not uppers or not rsis:
        return None

    # Alle Reihen ans Ende ausrichten (gleiche Laenge nehmen)
    min_len = min(len(uppers), len(rsis), len(closes))
    if min_len < 2:
        return None

    closes_aligned = closes[-min_len:]
    uppers = uppers[-min_len:]
    lowers = lowers[-min_len:]
    rsis = rsis[-min_len:]

    prev_close, last_close = closes_aligned[-2], closes_aligned[-1]
    prev_upper, prev_lower = uppers[-2], lowers[-2]
    prev_rsi = rsis[-2]

    # Rueckkehr von unten ins Band + vorher ueberverkauft
    if prev_close < prev_lower and last_close > prev_lower and prev_rsi < RSI_OVERSOLD:
        return "BUY", last_close, prev_rsi

    # Rueckkehr von oben ins Band + vorher ueberkauft
    if prev_close > prev_upper and last_close < prev_upper and prev_rsi > RSI_OVERBOUGHT:
        return "SELL", last_close, prev_rsi

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
        direction, price, rsi_value = signal
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"{emoji} {direction}-Signal auf {EPIC} (M1, Bollinger+RSI)\n"
            f"Kurs: {price:.2f}\n"
            f"RSI zum Signalzeitpunkt: {rsi_value:.1f}\n"
            f"Bitte manuell in der capital.com App prüfen und ggf. Order platzieren."
        )
        send_telegram(msg)
        print(f"Signal gesendet: {direction} @ {price:.2f} (RSI: {rsi_value:.1f})")
    else:
        print("Kein Signal.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
