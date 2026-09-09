import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf

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
    # Versuche zuerst Spot-Gold, sonst Futures
    df = pd.DataFrame()
    for ticker in ["XAUUSD=X", "GC=F"]:
        try:
            df = yf.download(tickers=ticker, period="1d", interval="1m", progress=False)
            if not df.empty and len(df) >= 25:
                print(f"Daten erfolgreich geladen für {ticker}")
                break
        except Exception as e:
            print(f"Fehler beim Laden von {ticker}: {e}")

    if df.empty or len(df) < 25:
        print("Keine ausreichenden Marktdaten erhalten.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 1. EMAs berechnen
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()

    # 2. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = (100 - (100 / (1 + rs))).fillna(50)

    # Letzte 2 Kerzen vergleichen
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close_p = float(latest['Close'])
    low_p = float(latest['Low'])
    high_p = float(latest['High'])
    
    ema9_cur = float(latest['EMA9'])
    ema21_cur = float(latest['EMA21'])
    ema9_prev = float(prev['EMA9'])
    ema21_prev = float(prev['EMA21'])
    
    rsi = float(latest['RSI'])

    # Bedingungen für Signale:
    # LONG: EMA9 schlägt EMA21 nach oben OR (Aufwärtstrend + Test der EMA21)
    bullish_cross = (ema9_prev <= ema21_prev) and (ema9_cur > ema21_cur)
    bullish_pullback = (ema9_cur > ema21_cur) and (low_p <= ema21_cur + 0.30) and (rsi >= 40)
    
    is_long = bullish_cross or bullish_pullback

    # SHORT: EMA9 schlägt EMA21 nach unten OR (Abwärtstrend + Test der EMA21)
    bearish_cross = (ema9_prev >= ema21_prev) and (ema9_cur < ema21_cur)
    bearish_pullback = (ema9_cur < ema21_cur) and (high_p >= ema21_cur - 0.30) and (rsi <= 60)

    is_short = bearish_cross or bearish_pullback

    if is_long:
        tp = close_p + 1.50
        sl = close_p - 1.00
        msg = (
            f"⚡ **GOLD 1M SCALP: LONG** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 9:** ${ema9_cur:.2f} | **EMA 21:** ${ema21_cur:.2f}\n"
            f"• **RSI (14):** {rsi:.1f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (+$1.50)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (-$1.00)"
        )
        send_telegram_message(msg)

    elif is_short:
        tp = close_p - 1.50
        sl = close_p + 1.00
        msg = (
            f"⚡ **GOLD 1M SCALP: SHORT** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 9:** ${ema9_cur:.2f} | **EMA 21:** ${ema21_cur:.2f}\n"
            f"• **RSI (14):** {rsi:.1f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (-$1.50)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (+$1.00)"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein Signal | Kurs: ${close_p:.2f} | EMA9: ${ema9_cur:.2f} | EMA21: ${ema21_cur:.2f} | RSI: {rsi:.1f}")

if __name__ == "__main__":
    check_gold_signals()
