import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf

# Telegram Bot Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            print("Telegram-Nachricht gesendet.")
        except Exception as e:
            print(f"Fehler bei Telegram: {e}")
    else:
        print(f"[CONSOLE] {message}")

def check_gold_signals():
    # 1m Daten laden
    ticker = "GC=F"
    df = yf.download(tickers=ticker, period="1d", interval="1m")

    if df.empty or len(df) < 50:
        print("Nicht genügend Daten empfangen.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 1. EMA Berechnungen (9 und 21)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()

    # 2. RSI (14) Berechnungen
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50)

    # Aktuelle Kerze und Vorherige Kerze prüfen
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close_p = float(latest['Close'])
    low_p = float(latest['Low'])
    high_p = float(latest['High'])
    ema9 = float(latest['EMA9'])
    ema21 = float(latest['EMA21'])
    rsi = float(latest['RSI'])

    # Long: Trend Up (EMA9 > EMA21), Low dipped to/below EMA21, RSI reset in 40-55
    is_long = (ema9 > ema21) and (low_p <= ema21) and (40 <= rsi <= 55)

    # Short: Trend Down (EMA9 < EMA21), High reached/above EMA21, RSI reset in 45-60
    is_short = (ema9 < ema21) and (high_p >= ema21) and (45 <= rsi <= 60)

    if is_long:
        msg = (
            f"⚡ **GOLD 1M SCALP: LONG** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 21 (Support):** ${ema21:.2f}\n"
            f"• **RSI (14):** {rsi:.1f}\n"
            f"• **Ziel:** TP +$2.00 / SL -$1.50"
        )
        send_telegram_message(msg)
    elif is_short:
        msg = (
            f"⚡ **GOLD 1M SCALP: SHORT** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 21 (Resist):** ${ema21:.2f}\n"
            f"• **RSI (14):** {rsi:.1f}\n"
            f"• **Ziel:** TP +$2.00 / SL -$1.50"
        )
        send_telegram_message(msg)
    else:
        print(f"Kein Signal | Kurs: ${close_p:.2f} | EMA9: ${ema9:.2f} | EMA21: ${ema21:.2f} | RSI: {rsi:.1f}")

if __name__ == "__main__":
    check_gold_signals()
