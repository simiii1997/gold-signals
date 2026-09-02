"""
Gold-Scalping SIGNAL-Bot (kein Auto-Trading!) - Momentum-Breakout
====================================================================

STRATEGIE (Trendfolge/Momentum, fuer haeufigere kleine Bewegungen):
- Schaut auf die letzten LOOKBACK M1-Kerzen (Standard: 10)
- BUY-Signal: aktueller Schlusskurs bricht ueber das Hoch dieser Kerzen
  aus (+ Mindestabstand in Punkten, um Mini-Ausbrueche zu filtern)
- SELL-Signal: aktueller Schlusskurs bricht unter das Tief dieser
  Kerzen aus

Das ist das Gegenteil von Mean-Reversion (Bollinger+RSI): hier wird
NICHT auf eine Umkehr gewartet, sondern eine beginnende Bewegung
moeglichst frueh mitgenommen. Dadurch entstehen mehr Signale, aber auch
mehr "Fehlausbrueche" (Kurs bricht kurz aus und faellt gleich zurueck
in die Range - sogenannte "Fakeouts").

Wichtiger Hinweis: Diese Strategie hat KEIN eingebautes Take-Profit/
Stop-Loss-Konzept in der Nachricht - du entscheidest bei jedem Signal
selbst, wie weit du die Bewegung mitgehen willst (z.B. feste 10 Punkte
Ziel, wie in deinem Beispiel 4370 -> 4380).

Benötigte GitHub Secrets (gleich geblieben):
    CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_EPIC
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import requests

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
EPIC = os.environ.get("CAPITAL_EPIC", "GOLD")

LOOKBACK = int(os.environ.get("LOOKBACK_CANDLES", "10"))
MIN_BREAKOUT_POINTS = float(os.environ.get("MIN_BREAKOUT_POINTS", "0.5"))

CANDLE_RESOLUTION = "MINUTE"  # M1 fuer schnelle Reaktion
CANDLE_COUNT = LOOKBACK + 10


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


def get_candles(cst, token):
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
    candles = []
    for c in prices:
        close = (c["closePrice"]["bid"] + c["closePrice"]["ask"]) / 2
        high = (c["highPrice"]["bid"] + c["highPrice"]["ask"]) / 2
        low = (c["lowPrice"]["bid"] + c["lowPrice"]["ask"]) / 2
        candles.append({"close": close, "high": high, "low": low})
    return candles


def decide_signal(candles):
    """
    Vergleicht die aktuelle (letzte) Kerze mit dem Hoch/Tief der
    LOOKBACK Kerzen DAVOR (die aktuelle Kerze selbst zaehlt nicht zur
    Range, sonst waere ein Ausbruch nie moeglich).
    """
    if len(candles) < LOOKBACK + 1:
        return None

    current = candles[-1]
    window = candles[-(LOOKBACK + 1):-1]  # die LOOKBACK Kerzen davor

    range_high = max(c["high"] for c in window)
    range_low = min(c["low"] for c in window)

    if current["close"] > range_high + MIN_BREAKOUT_POINTS:
        return "BUY", current["close"], range_high
    if current["close"] < range_low - MIN_BREAKOUT_POINTS:
        return "SELL", current["close"], range_low

    return None


def send_telegram(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
    resp.raise_for_status()


def main():
    cst, token = login()
    candles = get_candles(cst, token)
    signal = decide_signal(candles)

    if signal:
        direction, price, range_edge = signal
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"{emoji} {direction}-Momentum auf {EPIC} (M1, {LOOKBACK}er-Breakout)\n"
            f"Kurs: {price:.2f}\n"
            f"Ausbruch über/unter Range-Kante: {range_edge:.2f}\n"
            f"Bitte manuell in der capital.com App prüfen und ggf. Order platzieren."
        )
        send_telegram(msg)
        print(f"Signal gesendet: {direction} @ {price:.2f} (Range-Kante: {range_edge:.2f})")
    else:
        print("Kein Signal.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
