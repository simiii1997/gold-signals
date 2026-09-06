import pandas as pd
import numpy as np
import yfinance as yf
import requests
import os

# Telegram Bot Konfiguration (optional - setzt voraus, dass TOKENS als Secret hinterlegt sind)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Fehler beim Senden der Telegram-Nachricht: {e}")
    else:
        print(f"[SIGNAL ALERT] {message}")

def calculate_hoss_signals():
    # Gold-Daten abrufen (1-Minuten Intervall)
    ticker = "GC=F"
    df = yf.download(tickers=ticker, period="1d", interval="1m")

    if df.empty or len(df) < 300:
        print("Nicht genügend Daten empfangen.")
        return

    # Multi-Index Spalten aufräumen, falls yfinance sie so zurückgibt
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 1. VWAP & Deviation Berechnungen (300 Perioden)
    vwap_window = 300
    dev_mult = 1.5

    # Typischer Preis
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['PV'] = df['TP'] * df['Volume']

    # Gleitender VWAP über das Fenster
    df['VWAP'] = df['PV'].rolling(window=vwap_window).sum() / df['Volume'].rolling(window=vwap_window).sum()
    df['StdDev'] = df['Close'].rolling(window=vwap_window).std()

    df['UpperBand'] = df['VWAP'] + (df['StdDev'] * dev_mult)
    df['LowerBand'] = df['VWAP'] - (dev_mult * df['StdDev'])

    # 2. OBV (On Balance Volume) Berechnung
    df['PriceChange'] = df['Close'].diff()
    df['OBV_Direction'] = np.where(df['PriceChange'] > 0, 1, np.where(df['PriceChange'] < 0, -1, 0))
    df['OBV'] = (df['OBV_Direction'] * df['Volume']).cumsum()

    # 3. OBV RSI Berechnung (Länge = 5)
    rsi_length = 5
    delta = df['OBV'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_length).mean()

    rs = gain / loss
    df['OBV_RSI'] = 100 - (100 / (1 + rs))

    # Die aktuellste geschlossene Kerze prüfen (letzte vollständige Minute)
    latest = df.iloc[-1]
    close_price = latest['Close']
    low_price = latest['Low']
    high_price = latest['High']
    upper_band = latest['UpperBand']
    lower_band = latest['LowerBand']
    obv_rsi = latest['OBV_RSI']

    # Signal-Bedingungen prüfbar machen
    is_long = (low_price <= lower_band) and (obv_rsi <= 30)
    is_short = (high_price >= upper_band) and (obv_rsi >= 70)

    # Signale ausgeben/versenden
    if is_long:
        msg = f"🚀 **HOSS GOLD LONG SIGNAL**\nPreis: {close_price:.2f}\nUnterer Band-Touch: {lower_band:.2f}\nOBV RSI: {obv_rsi:.1f}"
        send_telegram_message(msg)
    elif is_short:
        msg = f"🔻 **HOSS GOLD SHORT SIGNAL**\nPreis: {close_price:.2f}\nOberer Band-Touch: {upper_band:.2f}\nOBV RSI: {obv_rsi:.1f}"
        send_telegram_message(msg)
    else:
        print(f"Kein Signal. Aktueller Gold-Kurs: {close_price:.2f} | OBV RSI: {obv_rsi:.1f}")

if __name__ == "__main__":
    calculate_hoss_signals()
