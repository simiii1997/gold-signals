import os
import requests
import numpy as np
import pandas as pd

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

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

def get_gold_data():
    # 1-Minuten-Intervall für direkte Scalping-Reaktion
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1min&outputsize=100&apikey={TWELVE_DATA_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "values" not in data:
            print(f"API Fehler: {data}")
            return pd.DataFrame()

        df = pd.DataFrame(data["values"])
        df = df.iloc[::-1].reset_index(drop=True)
        
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
            
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
        return df
    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return pd.DataFrame()

def check_gold_signals():
    df = get_gold_data()

    if df.empty or len(df) < 30:
        print("Keine ausreichenden Daten empfangen.")
        return

    # 1. EMAs berechnen (Schneller 9er und 21er)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()

    # 2. ATR (Volatilität)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=10).mean()

    # Wir betrachten die aktuellste geschlossene Kerze (Index -2)
    candle = df.iloc[-2]
    prev_candle = df.iloc[-3]

    close_p = candle['Close']
    open_p = candle['Open']
    ema9 = candle['EMA9']
    ema21 = candle['EMA21']
    
    prev_ema9 = prev_candle['EMA9']
    prev_ema21 = prev_candle['EMA21']

    # FANG-LOGIK: Reagiert wenn der Crossover in den letzten 2 Kerzen stattfand
    cross_up = (ema9 > ema21) and (prev_ema9 <= prev_ema21)
    cross_down = (ema9 < ema21) and (prev_ema9 >= prev_ema21)

    # Momentum-Bestätigung (Kerze schließt in Trendrichtung)
    is_long = cross_up and (close_p > open_p)
    is_short = cross_down and (close_p < open_p)

    if is_long:
        tp = close_p + 1.50
        sl = close_p - 1.00
        msg = (
            f"⚡ **GOLD SCALP: LONG SIGNAL** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 9/21 Crossover nach oben**\n\n"
            f"🎯 **TP:** ${tp:.2f} (+$1.50)\n"
            f"🛑 **SL:** ${sl:.2f} (-$1.00)"
        )
        send_telegram_message(msg)

    elif is_short:
        tp = close_p - 1.50
        sl = close_p + 1.00
        msg = (
            f"⚡ **GOLD SCALP: SHORT SIGNAL** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **EMA 9/21 Crossover nach unten**\n\n"
            f"🎯 **TP:** ${tp:.2f} (-$1.50)\n"
            f"🛑 **SL:** ${sl:.2f} (+$1.00)"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein Crossover | Kurs: ${close_p:.2f} | EMA9: ${ema9:.2f} | EMA21: ${ema21:.2f}")

if __name__ == "__main__":
    check_gold_signals()
