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
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1min&outputsize=30&apikey={TWELVE_DATA_API_KEY}"
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

    if df.empty or len(df) < 20:
        print("Keine ausreichenden Live-Daten empfangen.")
        return

    # Kerzenspannen berechnen
    df['Range'] = df['High'] - df['Low']
    
    # Durchschnittliche Kerzengröße der letzten 10 geschlossenen Kerzen
    avg_range_10 = df['Range'].iloc[-12:-2].mean()
    
    # 5-Minuten-Spannweite (ohne die aktuelle Kerze)
    highest_5 = df['High'].iloc[-7:-2].max()
    lowest_5 = df['Low'].iloc[-7:-2].min()

    # Wir betrachten die aktuellste vollständig abgeschlossene Kerze (Index -2)
    candle = df.iloc[-2]
    close_p = float(candle['Close'])
    open_p = float(candle['Open'])
    high_p = float(candle['High'])
    low_p = float(candle['Low'])
    candle_range = float(candle['Range'])

    # Dynamische Filter (deutlich empfindlicher):
    # 1. Kerze ist mindestens 40% größer als der 10m-Schnitt ODER mindestens $1.20 groß
    has_volatility = (candle_range >= avg_range_10 * 1.4) or (candle_range >= 1.20)
    
    # 2. Ausbruch aus dem 5m Hoch/Tief
    is_long = has_volatility and (close_p > highest_5) and (close_p > open_p)
    is_short = has_volatility and (close_p < lowest_5) and (close_p < open_p)

    if is_long:
        msg = (
            f"🚀 **GOLD BREAKOUT: LONG** 🚀\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **Kerzen-Spanne:** ${candle_range:.2f} (Schnitt: ${avg_range_10:.2f})\n"
            f"• **5m Hoch durchbrochen:** ${highest_5:.2f}\n\n"
            f"🎯 **TP:** +$2.00 | 🛑 **SL:** -$1.00"
        )
        send_telegram_message(msg)

    elif is_short:
        msg = (
            f"💥 **GOLD BREAKOUT: SHORT** 🔻\n\n"
            f"• **Kurs:** ${close_p:.2f}\n"
            f"• **Kerzen-Spanne:** ${candle_range:.2f} (Schnitt: ${avg_range_10:.2f})\n"
            f"• **5m Tief durchbrochen:** ${lowest_5:.2f}\n\n"
            f"🎯 **TP:** -$2.00 | 🛑 **SL:** +$1.00"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein Ausbruch | Kurs: ${close_p:.2f} | Kerzen-Spanne: ${candle_range:.2f} | Schnitt 10m: ${avg_range_10:.2f}")

if __name__ == "__main__":
    check_gold_signals()
