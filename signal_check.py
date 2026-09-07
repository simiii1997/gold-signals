import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf

# Telegram Bot Konfiguration (Nutzt die GitHub Repository Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message):
    """Sendet eine Benachrichtigung an den Telegram-Bot."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("Telegram-Nachricht erfolgreich gesendet.")
        except Exception as e:
            print(f"Fehler beim Senden der Telegram-Nachricht: {e}")
    else:
        print(f"[CONSOLE ALERT] {message}")


def calculate_hoss_signals():
    """Lädt 1m-Golddaten, berechnet VWAP-Bänder & OBV-RSI (mit 2-Kerzen-Toleranz)

    und versendet Signale.
    """
    # Gold-Futures Tick-Data (1-Minuten-Intervall)
    ticker = "GC=F"
    df = yf.download(tickers=ticker, period="1d", interval="1m")

    if df.empty or len(df) < 300:
        print(
            "Nicht genügend Marktdaten von yfinance empfangen. Versuch abgebrochen."
        )
        return

    # MultiIndex-Spalten von yfinance bereinigen (falls vorhanden)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # ==========================================
    # 1. VWAP & DEVIATION BERECHNUNG (300 Perioden)
    # ==========================================
    vwap_window = 300
    dev_mult = 1.5

    df["TP"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["PV"] = df["TP"] * df["Volume"]

    # Gleitender VWAP und Standardabweichung
    df["VWAP"] = (
        df["PV"].rolling(window=vwap_window).sum()
        / df["Volume"].rolling(window=vwap_window).sum()
    )
    df["StdDev"] = df["Close"].rolling(window=vwap_window).std()

    df["UpperBand"] = df["VWAP"] + (df["StdDev"] * dev_mult)
    df["LowerBand"] = df["VWAP"] - (df["StdDev"] * dev_mult)

    # ==========================================
    # 2. OBV & OBV-RSI BERECHNUNG (Länge = 5)
    # ==========================================
    df["PriceChange"] = df["Close"].diff()
    df["OBV_Direction"] = np.where(
        df["PriceChange"] > 0, 1, np.where(df["PriceChange"] < 0, -1, 0)
    )
    df["OBV"] = (df["OBV_Direction"] * df["Volume"]).cumsum()

    rsi_length = 5
    delta = df["OBV"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_length).mean()

    # Division durch Null abfangen
    rs = gain / loss.replace(0, np.nan)
    df["OBV_RSI"] = 100 - (100 / (1 + rs))
    df["OBV_RSI"] = df["OBV_RSI"].fillna(50)

    # ==========================================
    # 3. SIGNAL-PRÜFUNG MIT 2-KERZEN-TOLERANZ
    # ==========================================
    # Prüfe den RSI der letzten 3 Kerzen (aktuelle Minute + 2 davor)
    recent_rsi_max = df["OBV_RSI"].iloc[-3:].max()
    recent_rsi_min = df["OBV_RSI"].iloc[-3:].min()

    # Daten der aktuell geschlossenen Kerze
    latest = df.iloc[-1]
    close_price = float(latest["Close"])
    low_price = float(latest["Low"])
    high_price = float(latest["High"])
    upper_band = float(latest["UpperBand"])
    lower_band = float(latest["LowerBand"])
    current_rsi = float(latest["OBV_RSI"])

    # Bedingungen: Band berührt JETZT + RSI war in den letzten 2 Min extrem
    is_long = (low_price <= lower_band) and (recent_rsi_min <= 30)
    is_short = (high_price >= upper_band) and (recent_rsi_max >= 70)

    # ==========================================
    # 4. SIGNAL AUSGABE / TELEGRAM ALERT
    # ==========================================
    if is_long:
        msg = (
            f"🚀 **HOSS GOLD LONG SIGNAL**\n\n"
            f"• **Kurs:** ${close_price:.2f}\n"
            f"• **Unteres Band:** ${lower_band:.2f}\n"
            f"• **OBV RSI (Min 3m):** {recent_rsi_min:.1f}\n"
            f"• **Aktueller RSI:** {current_rsi:.1f}"
        )
        send_telegram_message(msg)

    elif is_short:
        msg = (
            f"🔻 **HOSS GOLD SHORT SIGNAL**\n\n"
            f"• **Kurs:** ${close_price:.2f}\n"
            f"• **Oberes Band:** ${upper_band:.2f}\n"
            f"• **OBV RSI (Max 3m):** {recent_rsi_max:.1f}\n"
            f"• **Aktueller RSI:** {current_rsi:.1f}"
        )
        send_telegram_message(msg)

    else:
        print(
            f"Kein Signal | Kurs: ${close_price:.2f} | Upper: ${upper_band:.2f} | "
            f"Lower: ${lower_band:.2f} | RSI: {current_rsi:.1f} (3m Max: {recent_rsi_max:.1f})"
        )


if __name__ == "__main__":
    calculate_hoss_signals()
