import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="Finviz Stock Comparison", layout="wide")

# 숫자를 소수점 한자리로 포맷팅하는 함수
def format_to_one_decimal(val):
    if val is None or val == '-' or val == '':
        return "-"
    
    suffix = ""
    num_str = str(val).replace(',', '').strip()
    
    # % 기호나 단위 기호(T, B, M, K) 처리
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

# 1. Finviz 데이터 스크래핑 함수
@st.cache_data(ttl=3600)
def get_finviz_data(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
    # 최신 브라우저 User-Agent 설정 (차단 방지)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Finviz의 핵심 지표가 담긴 테이블 탐색
        table = soup.find('table', class_='snapshot-table2')
        if not table:
            return None
        
        data = {"Ticker": ticker.upper()}
        
        # 가져올 항목 정의
        target_metrics = [
            "Market Cap", "Sales", "Income", "P/E", "Forward P/E", 
            "PEG", "P/S", "EPS next 5Y", "Oper. Margin", "ROIC", "EPS Q/Q", "Sales Q/Q"
        ]
        
        # 핵심 수정: Finviz는 'ROI'라는 라벨을 사용합니다.
        # 이를 UI에 표시할 'ROIC'로 매핑합니다.
        label_mapping = {"ROIC": "ROI"}
        
        cells = table.find_all('td')
        temp_dict = {}
        # 테이블의 td들을 순회하며 라벨-값 쌍을 저장
        for i in range(0, len(cells), 2):
            label = cells[i].text.strip()
            value = cells[i+1].text.strip()
            temp_dict[label] = value
            
        for metric in target_metrics:
            # 매핑 딕셔너리에 있으면 해당 라벨(ROI)로 찾고, 없으면 원래 이름(ROIC 등)으로 검색
            finviz_label = label_mapping.get(metric, metric)
            raw_value = temp_dict.get(finviz_label, "-")
            data[metric] = format_to_one_decimal(raw_value)
                
        return data
    except Exception:
        return None

# 2. yfinance를 이용한 3년 평균 P/E 계산 함수
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

# 시가총액 정렬용 파서
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

# UI 구성
st.title("📊 Tech Stock Benchmark Comparison")

user_ticker = st.text_input("비교할 종목 티커를 입력하세요:", placeholder="예: AAPL, TSLA").upper()

benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]
if user_ticker and user_ticker not in benchmarks:
    benchmarks.append(user_ticker)

if user_ticker:
    with st.spinner('데이터를 불러오는 중...'):
        all_data = []
        for t in benchmarks:
            fv_data = get_finviz_data(t)
            yf_data = get_yfinance_metrics(t)
            
            if fv_data:
                combined = {**fv_data, **yf_data}
                all_data.append(combined)
            time.sleep(0.1)

        if all_data:
            df = pd.DataFrame(all_data)
            
            ordered_cols = [
                "Ticker", "Market Cap", "Sales", "Income", 
                "P/E", "3yr avg P/E", "Forward P/E", 
                "PEG", "P/S", "EPS next 5Y", 
                "Oper. Margin", "ROIC", "EPS Q/Q", "Sales Q/Q"
            ]
            df = df[[c for c in ordered_cols if c in df.columns]]

            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])

            column_config = {col: st.column_config.Column(alignment="right") for col in df.columns if col != "Ticker"}

            def highlight_inserted(row):
                if row.Ticker == user_ticker:
                    return ['background-color: #3e4a5b; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_inserted, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            st.markdown(f"### 📈 {user_ticker} Monthly Chart")
            col1, _ = st.columns([2, 1])
            with col1:
                chart_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=c&ta=0&p=m&s=l"
                st.image(chart_url, use_container_width=True)
            
            st.markdown(f"---")
            st.caption(f"🔗 [Finviz에서 {user_ticker} 상세 정보 보기](https://finviz.com/quote.ashx?t={user_ticker})")
        else:
            st.error("데이터를 가져오지 못했습니다. 티커가 올바른지 확인해 주세요.")
