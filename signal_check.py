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

    # 1. Kerzenspannen (Range = High - Low) berechnen
    df['Range'] = df['High'] - df['Low']
    
    # Durchschnittliche Kerzengröße der letzten 10 Kerzen (ohne die aktuelle)
    avg_range_10 = df['Range'].iloc[-11:-1].mean()
    
    # Höchst-/Tiefstpreis der letzten 10 Kerzen
    highest_10 = df['High'].iloc[-11:-1].max()
    lowest_10 = df['Low'].iloc[-11:-1].min()

    latest = df.iloc[-1]
    close_p = float(latest['Close'])
    high_p = float(latest['High'])
    low_p = float(latest['Low'])
    current_range = float(latest['Range'])

    # 2. Ausbruchs-Bedingungen (Momentum / Volatilität)
    # Kerze muss mindestens 2.0x so groß sein wie der Schnitt + neues High/Low durchbrechen
    is_breakout_up = (current_range >= avg_range_10 * 2.0) and (high_p > highest_10) and (close_p > latest['Open'])
    is_breakout_down = (current_range >= avg_range_10 * 2.0) and (low_p < lowest_10) and (close_p < latest['Open'])

    if is_breakout_up:
        msg = (
            f"🚀 **STARKER GOLD BREAKOUT: LONG** 🚀\n\n"
            f"• **Aktueller Kurs:** ${close_p:.2f}\n"
            f"• **Kerzenspanne:** ${current_range:.2f} (Schnitt: ${avg_range_10:.2f})\n"
            f"• **10m Hoch durchbrochen:** ${highest_10:.2f}\n\n"
            f"⚠️ *Hohe Dynamik / Ausbruch nach oben!*"
        )
        send_telegram_message(msg)

    elif is_breakout_down:
        msg = (
            f"💥 **STARKER GOLD BREAKOUT: SHORT** 🔻\n\n"
            f"• **Aktueller Kurs:** ${close_p:.2f}\n"
            f"• **Kerzenspanne:** ${current_range:.2f} (Schnitt: ${avg_range_10:.2f})\n"
            f"• **10m Tief durchbrochen:** ${lowest_10:.2f}\n\n"
            f"⚠️ *Hohe Dynamik / Ausbruch nach unten!*"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein Breakout | Kurs: ${close_p:.2f} | Span: ${current_range:.2f} | Schnitt 10m: ${avg_range_10:.2f}")

if __name__ == "__main__":
    check_gold_signals()
