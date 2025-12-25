import streamlit as st
import yfinance as yf
import pandas as pd
import io
import zipfile
from datetime import datetime

# 設定網頁標題
st.set_page_config(page_title="大量股票數據批次下載器", page_icon="📦")
st.title('📦 台股/美股 批次資料下載器')
st.markdown("### 適合大量分析：一次輸入多檔代號，下載 ZIP 包，直接丟給 Gemini。")

# 1. 輸入區塊
col1, col2 = st.columns([3, 1])
with col1:
    # 支援換行或逗號分隔
    raw_tickers = st.text_area(
        "輸入股票代號 (用逗號或換行分隔)", 
        value="2330, 2317, 2454, NVDA, TSLA", 
        height=150
    )
with col2:
    period = st.selectbox("時間長度", ["1y", "3y", "5y", "10y"], index=1)
    st.markdown("---")
    st.caption("自動補全 .TW")

# 按鈕觸發
if st.button('🚀 開始批次抓取並打包'):
    # 處理輸入字串：取代逗號、換行，分割成清單
    tickers = [t.strip().upper() for t in raw_tickers.replace('\n', ',').split(',') if t.strip()]
    
    if not tickers:
        st.warning("請至少輸入一檔股票代號。")
    else:
        # 建立一個記憶體中的 ZIP 檔
        zip_buffer = io.BytesIO()
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        success_count = 0
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, ticker_symbol in enumerate(tickers):
                # 更新進度條
                status_text.text(f"正在下載 ({i+1}/{len(tickers)}): {ticker_symbol} ...")
                progress_bar.progress((i + 1) / len(tickers))
                
                # 自動補全台股代號
                real_ticker = ticker_symbol
                if ticker_symbol.isdigit():
                    real_ticker = f"{ticker_symbol}.TW"
                
                try:
                    # 下載數據
                    df = yf.download(real_ticker, period=period, interval="1d", progress=False)
                    
                    if not df.empty:
                        # 清洗數據
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df.reset_index(inplace=True)
                        
                        # 轉成 CSV 字串
                        csv_data = df.to_csv(index=False).encode('utf-8-sig')
                        
                        # 寫入 ZIP 檔 (檔名: 2330.TW.csv)
                        zf.writestr(f"{real_ticker}.csv", csv_data)
                        success_count += 1
                    else:
                        st.error(f"❌ {real_ticker} 查無資料")
                        
                except Exception as e:
                    st.error(f"❌ {real_ticker} 下載失敗: {e}")

        # 下載完成
        progress_bar.progress(100)
        status_text.text(f"處理完成！成功打包 {success_count} 檔股票。")
        
        if success_count > 0:
            # 讓 ZIP 指標回到開頭
            zip_buffer.seek(0)
            
            # 下載按鈕
            filename = f"Stock_Batch_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            st.download_button(
                label=f"📥 下載 ZIP 壓縮檔 ({success_count} 檔)",
                data=zip_buffer,
                file_name=filename,
                mime="application/zip"
            )
