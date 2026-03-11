import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Налаштування сторінки
st.set_page_config(page_title="Game Theory Trader", layout="wide")

st.title("📊 Інтрадей Термінал: Теорія Ігор")
st.sidebar.header("Налаштування стратегії")

# --- ЕЛЕМЕНТИ КЕРУВАННЯ ---
symbol = st.sidebar.selectbox("Оберіть актив", ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "NVDA"])
period = st.sidebar.slider("Період аналізу (дні)", 1, 7, 5)
window = st.sidebar.number_input("Вікно Z-Score (свічки)", value=200)
whale_sens = st.sidebar.slider("Чутливість до китів", 1.5, 4.0, 2.5)

@st.cache_data(ttl=300)
def get_data(symbol, period):
    try:
        data = yf.download(symbol, period=f"{period}d", interval='5m', progress=False, auto_adjust=True)
        if data.empty: return pd.DataFrame()
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        data = data.loc[:, ~data.columns.duplicated()].dropna()
        return data
    except Exception as e:
        st.error(f"Помилка завантаження: {e}")
        return pd.DataFrame()

data = get_data(symbol, period)

if not data.empty:
    # Очищуємо дані та готуємо індекс
    data.index = pd.to_datetime(data.index)
    
    # --- РОЗРАХУНКИ ---
    # Z-Score
    rolling_mean = data['Close'].rolling(window=int(window)).mean()
    rolling_std = data['Close'].rolling(window=int(window)).std()
    data['Z_Score'] = (data['Close'] - rolling_mean) / rolling_std

    # VWAP (Виправлений метод для стабільності)
    data['Date_Only'] = data.index.date
    def calc_vwap(group):
        vwap = (group['Close'] * group['Volume']).cumsum() / group['Volume'].cumsum()
        return vwap
    
    # Використовуємо transform, щоб уникнути проблем з індексами
    data['VWAP'] = data.groupby('Date_Only', group_keys=False)['Close'].transform(lambda x: calc_vwap(data.loc[x.index]))

    # Кити та Айсберги
    avg_vol = data['Volume'].rolling(20).mean()
    data['Whale'] = data['Volume'] > (avg_vol * whale_sens)
    price_change = data['Close'].pct_change().abs()
    data['Iceberg'] = (price_change < 0.0005) & (data['Volume'] > avg_vol * 1.8)

    final_df = data.dropna(subset=['Z_Score', 'VWAP']).copy()

    # --- ВІЗУАЛІЗАЦІЯ ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    plt.subplots_adjust(hspace=0.05)

    # 1. Графік ціни
    ax1.plot(final_df.index, final_df['Close'], label='Price (5m)', color='black', alpha=0.6)
    ax1.plot(final_df.index, final_df['VWAP'], label='Intraday VWAP', color='orange', lw=2)
    
    whales = final_df[final_df['Whale']]
    icebergs = final_df[final_df['Iceberg']]
    ax1.scatter(whales.index, whales['Close'], color='red', label='Whale', s=60, marker='^', zorder=5)
    ax1.scatter(icebergs.index, icebergs['Close'], color='blue', label='Iceberg Wall', s=60, marker='s', zorder=5)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.2)

    # 2. Графік Z-Score
    ax2.plot(final_df.index, final_df['Z_Score'], color='purple', label='Z-Score', lw=1.5)
    ax2.axhline(2.5, color='red', ls='--', alpha=0.5)
    ax2.axhline(-2.5, color='green', ls='--', alpha=0.5)
    ax2.fill_between(final_df.index, 2.5, final_df['Z_Score'], where=(final_df['Z_Score'] > 2.5), color='red', alpha=0.2)
    ax2.fill_between(final_df.index, -2.5, final_df['Z_Score'], where=(final_df['Z_Score'] < -2.5), color='green', alpha=0.2)
    
    # Налаштування часу (X-axis)
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d-%m'))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    ax2.grid(True, which='major', alpha=0.3)
    ax2.grid(True, which='minor', alpha=0.1, ls=':')

    st.pyplot(fig)

    # --- СТАТИСТИЧНА ПАНЕЛЬ ---
    col1, col2, col3 = st.columns(3)
    last = final_df.iloc[-1]

    with col1:
        st.metric("Поточна ціна", f"${last['Close']:.2f}")
    with col2:
        st.metric("Z-Score (Відхилення)", f"{last['Z_Score']:.2f}")
    with col3:
        if last['Z_Score'] > 2.5:
            st.error("🔔 ПРОДАЖ (Перегрів)")
        elif last['Z_Score'] < -2.5:
            st.success("🔔 КУПІВЛЯ (Паніка)")
        else:
            st.info("⚖️ Рівновага")

    if last['Whale']:
        st.warning("🐳 Виявлено активність кита!")
    if last['Iceberg']:
        st.info("🧊 Виявлено ознаки 'Айсберга'!")

else:
    st.error("Дані відсутні. Спробуйте змінити період або актив.")
