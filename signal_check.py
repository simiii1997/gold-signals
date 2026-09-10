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
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1min&outputsize=20&apikey={TWELVE_DATA_API_KEY}"
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
        print(f"Fehler beim Abrufen der Daten: {e}")
        return pd.DataFrame()

def check_gold_signals():
    df = get_gold_data()

    if df.empty or len(df) < 10:
        print("Keine ausreichenden Live-Daten empfangen.")
        return

    # Letzte vollendete Kerze (Index -2)
    candle = df.iloc[-2]
    close_p = float(candle['Close'])
    open_p = float(candle['Open'])

    # Hochs und Tiefs der 5 Kerzen DAVOR (Index -7 bis -2)
    highest_5 = df['High'].iloc[-7:-2].max()
    lowest_5 = df['Low'].iloc[-7:-2].min()

    # Reine Breakout-Logik
    is_long = (close_p > highest_5) and (close_p > open_p)
    is_short = (close_p < lowest_5) and (close_p < open_p)

    if is_long:
        tp = close_p + 1.50
        sl = close_p - 1.00
        msg = (
            f"🚀 **GOLD BREAKOUT: LONG** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **5m High Durchbrochen:** ${highest_5:.2f}\n\n"
            f"🎯 **TP:** ${tp:.2f} (+$1.50)\n"
            f"🛑 **SL:** ${sl:.2f} (-$1.00)"
        )
        send_telegram_message(msg)

    elif is_short:
        tp = close_p - 1.50
        sl = close_p + 1.00
        msg = (
            f"💥 **GOLD BREAKOUT: SHORT** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **5m Low Durchbrochen:** ${lowest_5:.2f}\n\n"
            f"🎯 **TP:** ${tp:.2f} (-$1.50)\n"
            f"🛑 **SL:** ${sl:.2f} (+$1.00)"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein Breakout | Kurs: ${close_p:.2f} | 5m High: ${highest_5:.2f} | 5m Low: ${lowest_5:.2f}")

if __name__ == "__main__":
    check_gold_signals()
