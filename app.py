import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import yfinance as yf

# 1. 페이지 설정
st.set_page_config(page_title="Finviz Stock Comparison", layout="wide")

# 숫자를 소수점 한자리로 포맷팅하는 함수
def format_to_one_decimal(val):
    if val is None or val == '-' or val == '' or str(val).lower() == 'nan':
        return "-"
    
    suffix = ""
    num_str = str(val).replace(',', '').strip()
    
    if num_str.endswith('%'):
        suffix = '%'
        num_str = num_str[:-1]
    elif len(num_str) > 1 and num_str[-1].upper() in ['T', 'B', 'M', 'K']:
        suffix = num_str[-1].upper()
        num_str = num_str[:-1]
    
    try:
        return f"{float(num_str):.1f}{suffix}"
    except ValueError:
        return val

# 2. Finviz 데이터 스크래핑 함수
@st.cache_data(ttl=3600)
def get_finviz_data(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='snapshot-table2')
        if not table:
            return None
        
        cells = table.find_all('td')
        temp_dict = {cells[i].text.strip(): cells[i+1].text.strip() for i in range(0, len(cells), 2)}
        
        data = {"Ticker": ticker.upper()}
        
        # Finviz 사이트의 실제 라벨 명칭(ROI)을 고려하여 매핑
        target_map = {
            "Market Cap": "Market Cap",
            "Sales": "Sales",
            "Income": "Income",
            "P/E": "P/E",
            "Forward P/E": "Forward P/E",
            "PEG": "PEG",
            "P/S": "P/S",
            "EPS next 5Y": "EPS next 5Y",
            "Oper. Margin": "Oper. Margin",
            "ROIC": "ROI", # Finviz에서는 ROI로 표시됨
            "EPS Q/Q": "EPS Q/Q",
            "Sales Q/Q": "Sales Q/Q"
        }
            
        for display_name, finviz_label in target_map.items():
            raw_val = temp_dict.get(finviz_label, "-")
            data[display_name] = format_to_one_decimal(raw_val)
                
        return data
    except Exception:
        return None

# 3. yfinance를 이용한 3년 평균 P/E 계산 함수
@st.cache_data(ttl=3600)
def get_yfinance_metrics(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3y")
        if stock.financials is None or stock.financials.empty:
            return {"3yr avg P/E": "-"}
            
        fin = stock.financials.T
        if not hist.empty and 'Net Income' in fin.columns:
            avg_price = hist['Close'].mean()
            avg_net_income = fin['Net Income'].head(3).mean() 
            shares = stock.info.get('sharesOutstanding')
            
            if avg_net_income and shares and avg_net_income > 0:
                eps_avg = avg_net_income / shares
                return {"3yr avg P/E": f"{avg_price / eps_avg:.1f}"}
    except Exception:
        pass
    return {"3yr avg P/E": "-"}

# 시가총액 정렬용 숫자 변환기
def parse_market_cap(val):
    if val == '-' or not val: return 0
    val = str(val).replace(',', '').upper()
    multiplier = 1
    if 'T' in val: multiplier = 1e12
    elif 'B' in val: multiplier = 1e9
    elif 'M' in val: multiplier = 1e6
    try:
        num_part = ''.join(c for c in val if c.isdigit() or c == '.')
        return float(num_part) * multiplier
    except: return 0

# --- UI 레이아웃 ---
st.title("📊 다중 종목 벤치마크 분석")

# [수정] 입력창은 단 하나만 유지합니다.
user_input_raw = st.text_input(
    "비교할 종목 티커들을 입력하세요 (최대 3개, 콤마로 구분):", 
    placeholder="예: APH, TEL, EQT",
    key="multi_ticker_input_main"
).upper()

# [수정] 입력된 문자열을 콤마 기준으로 정확히 분리하여 리스트로 만듭니다.
input_tickers = [t.strip() for t in user_input_raw.split(",") if t.strip()][:3]

# 기본 비교 대상 리스트
benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]

# 사용자가 입력한 티커들을 비교 리스트에 병합 (중복 방지)
final_ticker_list = benchmarks.copy()
for t in input_tickers:
    if t not in final_ticker_list:
        final_ticker_list.append(t)

if input_tickers:
    with st.spinner('실시간 데이터를 수집하는 중...'):
        all_data = []
        for t in final_ticker_list:
            fv_data = get_finviz_data(t)
            yf_data = get_yfinance_metrics(t)
            
            if fv_data:
                combined = {**fv_data, **yf_data}
                all_data.append(combined)
            time.sleep(0.1) # 서버 부하 방지용 지연

        if all_data:
            df = pd.DataFrame(all_data)
            
            # 컬럼 순서 설정
            ordered_cols = [
                "Ticker", "Market Cap", "Sales", "Income", 
                "P/E", "3yr avg P/E", "Forward P/E", 
                "PEG", "P/S", "EPS next 5Y", 
                "Oper. Margin", "ROIC", "EPS Q/Q", "Sales Q/Q"
            ]
            df = df[[c for c in ordered_cols if c in df.columns]]

            # 시가총액 기준 정렬
            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])

            # 테이블 스타일링
            column_config = {col: st.column_config.Column(alignment="right") for col in df.columns if col != "Ticker"}

            def highlight_input_tickers(row):
                if row.Ticker in input_tickers:
                    return ['background-color: #3e4a5b; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_input_tickers, axis=1),
                width="stretch", 
                hide_index=True,
                column_config=column_config
            )
            
            st.markdown("---")
            
            # [수정] 하단 차트 섹션: 입력된 티커 개수만큼 컬럼을 나누어 각각 표시
            st.subheader("📈 Monthly Charts")
            chart_cols = st.columns(len(input_tickers))
            for i, t in enumerate(input_tickers):
                with chart_cols[i]:
                    st.markdown(f"#### {t}")
                    chart_url = f"https://charts2.finviz.com/chart.ashx?t={t}&ty=c&ta=0&p=m&s=l"
                    st.image(chart_url, width="stretch")
                    st.caption(f"🔗 [Finviz {t} 바로가기](https://finviz.com/quote.ashx?t={t})")
            
        else:
            st.error("데이터를 불러오지 못했습니다. 티커가 정확한지 확인해 주세요.")
