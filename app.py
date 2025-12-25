import streamlit as st
import yfinance as yf
import pandas as pd
import io
import zipfile
from datetime import datetime
from FinMind.data import DataLoader

# 設定網頁標題
st.set_page_config(page_title="全方位股票籌碼下載器", page_icon="📦")
st.title('📦 台股/美股 籌碼與數據下載器')
st.markdown("### 批次分析：一次輸入多檔代號，下載包含「法人、資券、大戶」的 CSV。")

# ==========================================
#  區塊 1: 股票批次下載 (原有功能 - 日線+籌碼)
# ==========================================
st.subheader("1. 股票批次下載 (日線 + 籌碼)")

col1, col2 = st.columns([3, 1])
with col1:
    # 支援換行或逗號分隔
    raw_tickers = st.text_area(
        "輸入股票代號 (用逗號或換行分隔)", 
        value="2330, 2317, 2454, NVDA, TSLA", 
        height=150
    )
with col2:
    period = st.selectbox("時間長度", ["1y", "3y", "5y", "10y"], index=0)
    st.markdown("---")
    st.caption("自動補全 .TW")

# 按鈕觸發
if st.button('🚀 開始批次抓取並打包 (Stocks)'):
    tickers = [t.strip().upper() for t in raw_tickers.replace('\n', ',').split(',') if t.strip()]
    
    if not tickers:
        st.warning("請至少輸入一檔股票代號。")
    else:
        zip_buffer = io.BytesIO()
        progress_bar = st.progress(0)
        status_text = st.empty()
        success_count = 0
        
        # 初始化 FinMind Loader
        fm = DataLoader()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, ticker_symbol in enumerate(tickers):
                status_text.text(f"正在下載 ({i+1}/{len(tickers)}): {ticker_symbol} ...")
                progress_bar.progress((i + 1) / len(tickers))
                
                # 判斷是否為台股 (全數字為台股)
                is_tw_stock = ticker_symbol.isdigit()
                
                real_ticker = ticker_symbol
                stock_id_only = ticker_symbol
                
                if is_tw_stock:
                    real_ticker = f"{ticker_symbol}.TW"
                
                try:
                    # 1. 下載股價 (YFinance - 台美股通用)
                    df = yf.download(real_ticker, period=period, interval="1d", progress=False)
                    
                    if not df.empty:
                        # 基礎清洗
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df.reset_index(inplace=True)
                        if 'Date' in df.columns:
                            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)

                        # 🛡️ 安全初始化：先建立空欄位 (防呆)
                        chip_cols = [
                            'Foreign_Net', 'Trust_Net', 'Dealer_Net', # 三大法人
                            'Margin_Balance', 'Short_Balance',        # 融資券
                            'Big_Hands_Pct', 'Small_Hands_Pct',       # 集保分佈
                            'Chip_Spread'                             # 籌碼差
                        ]
                        for c in chip_cols:
                            df[c] = 0.0

                        # 🇹🇼 台股專屬：抓取 FinMind 籌碼
                        if is_tw_stock:
                            try:
                                start_date = (datetime.now() - pd.DateOffset(years=5)).strftime('%Y-%m-%d')
                                
                                # A. 三大法人
                                df_inst = fm.taiwan_stock_institutional_investors(stock_id=stock_id_only, start_date=start_date)
                                if not df_inst.empty:
                                    df_inst['date'] = pd.to_datetime(df_inst['date'])
                                    pivot = df_inst.pivot_table(index='date', columns='name', values=['buy', 'sell'], aggfunc='sum').fillna(0)
                                    
                                    def get_net(name):
                                        if name in pivot['buy'] and name in pivot['sell']:
                                            return pivot['buy'][name] - pivot['sell'][name]
                                        return 0
                                    
                                    temp_df = pd.DataFrame(index=pivot.index)
                                    temp_df['Foreign_Net'] = get_net('Foreign_Investor')
                                    temp_df['Trust_Net'] = get_net('Investment_Trust')
                                    temp_df['Dealer_Net'] = get_net('Dealer_Self_Analysis')
                                    
                                    df.set_index('Date', inplace=True)
                                    df.update(temp_df)
                                    df.reset_index(inplace=True)

                                # B. 融資融券
                                df_margin = fm.taiwan_stock_margin_purchase_short_sale(stock_id=stock_id_only, start_date=start_date)
                                if not df_margin.empty:
                                    df_margin['date'] = pd.to_datetime(df_margin['date'])
                                    df_margin.set_index('date', inplace=True)
                                    df_margin.rename(columns={'MarginPurchaseTodayBalance': 'Margin_Balance', 'ShortSaleTodayBalance': 'Short_Balance'}, inplace=True)
                                    
                                    df.set_index('Date', inplace=True)
                                    df.update(df_margin[['Margin_Balance', 'Short_Balance']])
                                    df.reset_index(inplace=True)

                                # C. 集保股權分散
                                df_holding = fm.taiwan_stock_holding_shares_per(stock_id=stock_id_only, start_date=start_date)
                                if not df_holding.empty:
                                    df_holding['date'] = pd.to_datetime(df_holding['date'])
                                    df_holding['percent'] = pd.to_numeric(df_holding['percent'], errors='coerce')
                                    df_holding['HoldingSharesLevel'] = pd.to_numeric(df_holding['HoldingSharesLevel'], errors='coerce')
                                    
                                    grp = df_holding.groupby('date')
                                    big = grp.apply(lambda x: x[x['HoldingSharesLevel'] >= 12]['percent'].sum())
                                    small = grp.apply(lambda x: x[x['HoldingSharesLevel'] <= 3]['percent'].sum())
                                    
                                    temp_hold = pd.DataFrame({'Big_Hands_Pct': big, 'Small_Hands_Pct': small})
                                    temp_hold['Chip_Spread'] = temp_hold['Big_Hands_Pct'] - temp_hold['Small_Hands_Pct']
                                    
                                    df.set_index('Date', inplace=True)
                                    df = pd.merge(df, temp_hold, left_index=True, right_index=True, how='left', suffixes=('', '_new'))
                                    for col in ['Big_Hands_Pct', 'Small_Hands_Pct', 'Chip_Spread']:
                                        if f'{col}_new' in df.columns:
                                            df[col] = df[f'{col}_new'].combine_first(df[col])
                                            df.drop(columns=[f'{col}_new'], inplace=True)
                                    df.reset_index(inplace=True)
                                    df[['Big_Hands_Pct', 'Small_Hands_Pct', 'Chip_Spread']] = df[['Big_Hands_Pct', 'Small_Hands_Pct', 'Chip_Spread']].ffill()

                            except Exception as e:
                                print(f"FinMind Warning: {e}")
                                pass

                        # 🧮 通用指標
                        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0)
                        df['Main_Force_Net'] = df['Foreign_Net'] + df['Trust_Net'] + df['Dealer_Net']
                        df['Concentration_5'] = (df['Main_Force_Net'].rolling(5).sum() / (df['Volume'].rolling(5).sum() + 1e-9) * 100).round(2)
                        df['Concentration_20'] = (df['Main_Force_Net'].rolling(20).sum() / (df['Volume'].rolling(20).sum() + 1e-9) * 100).round(2)
                        
                        close_diff = df['Close'].diff()
                        df['Raw_Force'] = close_diff * df['Volume']
                        df['EFI_13'] = df['Raw_Force'].ewm(span=13, adjust=False).mean()

                        # 存檔
                        df.fillna(0, inplace=True)
                        csv_data = df.to_csv(index=False).encode('utf-8-sig')
                        zf.writestr(f"{real_ticker}.csv", csv_data)
                        success_count += 1
                        
                    else:
                        st.error(f"❌ {real_ticker} 查無資料")
                except Exception as e:
                    st.error(f"❌ {real_ticker} 下載失敗: {e}")

        progress_bar.progress(100)
        status_text.text(f"處理完成！成功打包 {success_count} 檔股票。")
        
        if success_count > 0:
            zip_buffer.seek(0)
            filename = f"Stock_Batch_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            st.download_button(
                label=f"📥 下載 ZIP 壓縮檔 ({success_count} 檔)",
                data=zip_buffer,
                file_name=filename,
                mime="application/zip"
            )

# ==========================================
#  區塊 2: 台指期專屬下載 (新增功能)
# ==========================================
st.markdown("---")
st.subheader("2. ⏱️ 台指期 (WTX) 小時 K 下載")
st.info("💡 下載近 730 天 (約2年) 的連續月台指期貨資料，週期為 1 小時 (1h)。適合上傳進行「日線+小時線」雙週期分析。")

if st.button("🚀 下載台指期 (WTX=F) 小時 K"):
    
    ticker_futures = "WTX=F" # Yahoo Finance 台指期連續月代號
    
    with st.spinner(f'正在下載 {ticker_futures} 小時線資料...'):
        try:
            # 強制設定：1小時, 2年 (Yahoo API 限制)
            df_futures = yf.download(ticker_futures, period="2y", interval="1h", progress=False)
            
            if not df_futures.empty:
                # 數據清洗
                if isinstance(df_futures.columns, pd.MultiIndex):
                    df_futures.columns = df_futures.columns.get_level_values(0)
                df_futures.reset_index(inplace=True)
                
                # 轉換為 CSV
                csv_futures = df_futures.to_csv(index=False).encode('utf-8-sig')
                
                st.success(f"✅ 下載成功！資料區間：{df_futures['Datetime'].min()} 至 {df_futures['Datetime'].max()}")
                
                # 獨立下載按鈕
                filename_futures = f"WTX_Hourly_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                st.download_button(
                    label="📥 點擊下載 WTX_Hourly.csv",
                    data=csv_futures,
                    file_name=filename_futures,
                    mime="text/csv"
                )
            else:
                st.error("❌ 下載失敗，Yahoo Finance 暫無數據 (可能是連線問題)。")
                
        except Exception as e:
            st.error(f"❌ 發生錯誤: {e}")
