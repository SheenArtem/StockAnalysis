# filename: technical_analysis.py

import yfinance as yf
import mplfinance as mpf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def calculate_indicators(df):
    """將指標計算邏輯獨立出來，供不同週期共用"""
    # A. 基礎均線
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()

    # B. 布林通道
    df['std20'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['MA20'] + (2 * df['std20'])
    df['BB_Lo'] = df['MA20'] - (2 * df['std20'])

    # C. ATR
    prev_close = df['Close'].shift(1)
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - prev_close)
    df['L-PC'] = abs(df['Low'] - prev_close)
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['ATR_Stop'] = df['Close'] - (2 * df['ATR'])

    # D. MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    # E. KD
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = df['RSV'].ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    # F. 成交量判斷 (簡單量增)
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()

    return df

def plot_single_chart(ticker, df, title_suffix, timeframe_label):
    """繪製單張圖表的共用函式"""
    # 裁切數據 (日線看近半年，週線看近兩年，避免圖形太擠)
    if timeframe_label == 'Weekly':
        plot_df = df.tail(100).copy() # 週線看約 2 年
    else:
        plot_df = df.tail(120).copy() # 日線看約半年
        
    apds = [
        # 主圖: 均線 + 布林
        mpf.make_addplot(plot_df[['MA5', 'MA10', 'MA20']], ax=None, width=1.0),
        mpf.make_addplot(plot_df['MA60'], color='black', width=1.5), 
        mpf.make_addplot(plot_df['BB_Up'], color='gray', linestyle='--', alpha=0.5),
        mpf.make_addplot(plot_df['BB_Lo'], color='gray', linestyle='--', alpha=0.5),
        # ATR (僅日線顯示，避免週線混亂)
        # mpf.make_addplot(plot_df['ATR_Stop'], type='scatter', markersize=5, marker='_', color='purple'),

        # 副圖 1: MACD
        mpf.make_addplot(plot_df['Hist'], type='bar', panel=1, color='dimgray', alpha=0.5, title='MACD'),
        mpf.make_addplot(plot_df['MACD'], panel=1, color='fuchsia'),
        mpf.make_addplot(plot_df['Signal'], panel=1, color='c'),

        # 副圖 2: KD
        mpf.make_addplot(plot_df['K'], panel=2, color='orange', title='KD'),
        mpf.make_addplot(plot_df['D'], panel=2, color='blue'),
    ]

    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, style='yahoo', grid_style=':')

    print(f"📊 正在繪製 {timeframe_label} K線圖...")
    mpf.plot(plot_df, type='candle', style=s, addplot=apds, 
             volume=True, 
             panel_ratios=(3, 1, 1), 
             title=f"{ticker} {title_suffix} ({timeframe_label})", 
             figsize=(10, 10), # 正方形一點比較好在手機看
             tight_layout=True)

def plot_dual_timeframe(ticker_symbol):
    """
    主程式：一次生成兩張圖 (週線 + 日線)
    """
    # 1. 處理代號
    ticker_symbol = str(ticker_symbol).strip()
    if ticker_symbol.isdigit():
        ticker = f"{ticker_symbol}.TW"
    else:
        ticker = ticker_symbol.upper()

    print(f"🚀 開始分析 {ticker} 的長短週期...")

    # 2. 下載並處理 [週線 Weekly]
    # 週線抓 3 年數據，確保均線計算足夠
    df_week = yf.download(ticker, period='3y', interval='1wk', progress=False)
    if isinstance(df_week.columns, pd.MultiIndex): df_week.columns = df_week.columns.get_level_values(0)
    
    if not df_week.empty:
        df_week = calculate_indicators(df_week)
        plot_single_chart(ticker, df_week, "Long Term Trend", "Weekly")
    else:
        print("❌ 無法取得週線資料")

    # 3. 下載並處理 [日線 Daily]
    # 日線抓 1 年數據
    df_day = yf.download(ticker, period='1y', interval='1d', progress=False)
    if isinstance(df_day.columns, pd.MultiIndex): df_day.columns = df_day.columns.get_level_values(0)

    if not df_day.empty:
        df_day = calculate_indicators(df_day)
        plot_single_chart(ticker, df_day, "Short Term Action", "Daily")
    else:
        print("❌ 無法取得日線資料")

if __name__ == "__main__":
    # 測試用
    plot_dual_timeframe('2330')
