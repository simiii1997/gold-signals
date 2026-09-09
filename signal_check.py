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
    # Spot Gold Ticker
    ticker = "XAUUSD=X"
    df = yf.download(tickers=ticker, period="1d", interval="1m")

    if df.empty or len(df) < 15:
        print("Nicht genügend Daten empfangen.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 1. RSI (14) zur Momentum-Bestätigung
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50)

    # 2. Highs & Lows der letzten 5 Kerzen (ohne die aktuellste)
    df['High_5'] = df['High'].shift(1).rolling(window=5).max()
    df['Low_5'] = df['Low'].shift(1).rolling(window=5).min()

    latest = df.iloc[-1]

    close_p = float(latest['Close'])
    high_5 = float(latest['High_5'])
    low_5 = float(latest['Low_5'])
    rsi = float(latest['RSI'])

    # LONG: Aktueller Preis bricht das 5-Minuten-Hoch + RSI zeigt Stärke (> 52)
    is_long = (close_p > high_5) and (rsi > 52)

    # SHORT: Aktueller Preis bricht das 5-Minuten-Tief + RSI zeigt Schwäche (< 48)
    is_short = (close_p < low_5) and (rsi < 48)

    if is_long:
        tp = close_p + 1.50
        sl = close_p - 1.00
        msg = (
            f"⚡ **GOLD BREAKOUT: LONG** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **5m High Durchbrochen:** ${high_5:.2f}\n"
            f"• **RSI:** {rsi:.1f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (+$1.50)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (-$1.00)"
        )
        send_telegram_message(msg)

    elif is_short:
        tp = close_p - 1.50
        sl = close_p + 1.00
        msg = (
            f"⚡ **GOLD BREAKOUT: SHORT** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **5m Low Durchbrochen:** ${low_5:.2f}\n"
            f"• **RSI:** {rsi:.1f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (-$1.50)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (+$1.00)"
        )
        send_telegram_message(msg)

    else:
        print(f"Warten auf Breakout | Kurs: ${close_p:.2f} | 5m-High: ${high_5:.2f} | 5m-Low: ${low_5:.2f} | RSI: {rsi:.1f}")

if __name__ == "__main__":
    check_gold_signals()
