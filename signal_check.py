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
    # 3-Minuten Intervall für deutlich höhere Signal-Qualität beim Gold-Scalping
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=3min&outputsize=250&apikey={TWELVE_DATA_API_KEY}"
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

    if df.empty or len(df) < 200:
        print("Keine ausreichenden Daten (mind. 200 Kerzen für EMA200 benötigt).")
        return

    # 1. EMA 200 für den übergeordneten Trend
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # 2. UT Bot Alerts Berechnungen (Key: 1.0, ATR: 10)
    key_sensitivity = 1.0
    atr_period = 10

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=atr_period).mean()

    df['xATRTrailingStop'] = 0.0
    df['pos'] = 0

    for i in range(1, len(df)):
        prev_stop = df.loc[i-1, 'xATRTrailingStop']
        prev_close = df.loc[i-1, 'Close']
        curr_close = df.loc[i, 'Close']
        nLoss = key_sensitivity * df.loc[i, 'ATR']

        if curr_close > prev_stop and prev_close > prev_stop:
            df.loc[i, 'xATRTrailingStop'] = max(prev_stop, curr_close - nLoss)
        elif curr_close < prev_stop and prev_close < prev_stop:
            df.loc[i, 'xATRTrailingStop'] = min(prev_stop, curr_close + nLoss)
        elif curr_close > prev_stop:
            df.loc[i, 'xATRTrailingStop'] = curr_close - nLoss
        else:
            df.loc[i, 'xATRTrailingStop'] = curr_close + nLoss

        if prev_close < prev_stop and curr_close > prev_stop:
            df.loc[i, 'pos'] = 1
        elif prev_close > prev_stop and curr_close < prev_stop:
            df.loc[i, 'pos'] = -1
        else:
            df.loc[i, 'pos'] = df.loc[i-1, 'pos']

    # Betrachte die letzte VOLLSTÄNDIG GESCHLOSSENE Kerze (Index -2)
    candle = df.iloc[-2]
    prev_candle = df.iloc[-3]

    close_p = candle['Close']
    ema200 = candle['EMA200']
    
    curr_pos = candle['pos']
    prev_pos = prev_candle['pos']

    # Trend-Gefilterte Einstiege:
    # BUY nur wenn UT Bot anschlägt UND der Kurs ÜBER dem EMA 200 steht
    is_buy = (curr_pos == 1) and (prev_pos != 1) and (close_p > ema200)
    
    # SELL nur wenn UT Bot anschlägt UND der Kurs UNTER dem EMA 200 steht
    is_sell = (curr_pos == -1) and (prev_pos != -1) and (close_p < ema200)

    if is_buy:
        tp = close_p + 3.00
        sl = close_p - 2.00
        msg = (
            f"🎯 **UT BOT PRO: BUY (LONG)** 🚀\n\n"
            f"• **Einstiegskurs:** ${close_p:.2f}\n"
            f"• **EMA 200 Trend:** Bullisch (${ema200:.2f})\n"
            f"• **Trailing Stop:** ${candle['xATRTrailingStop']:.2f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (+$3.00)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (-$2.00)"
        )
        send_telegram_message(msg)

    elif is_sell:
        tp = close_p - 3.00
        sl = close_p + 2.00
        msg = (
            f"🎯 **UT BOT PRO: SELL (SHORT)** 🔻\n\n"
            f"• **Einstiegskurs:** ${close_p:.2f}\n"
            f"• **EMA 200 Trend:** Bärisch (${ema200:.2f})\n"
            f"• **Trailing Stop:** ${candle['xATRTrailingStop']:.2f}\n\n"
            f"🎯 **Take Profit:** ${tp:.2f} (-$3.00)\n"
            f"🛑 **Stop Loss:** ${sl:.2f} (+$2.00)"
        )
        send_telegram_message(msg)

    else:
        print(f"Kein gefiltertes Signal | Kurs: ${close_p:.2f} | EMA200: ${ema200:.2f} | Trend: {'LONG' if curr_pos == 1 else 'SHORT'}")

if __name__ == "__main__":
    check_gold_signals()
