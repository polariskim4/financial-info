import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# 페이지 설정
st.set_page_config(page_title="Finviz Stock Comparison", layout="wide")

# 숫자를 소수점 한자리로 포맷팅하는 함수
def format_to_one_decimal(val):
    if not val or val == '-':
        return val
    suffix = ""
    num_str = val.replace(',', '')
    
    if num_str.endswith('%'):
        suffix = '%'
        num_str = num_str[:-1]
    elif num_str[-1].upper() in ['T', 'B', 'M', 'K'] and len(num_str) > 1:
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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='snapshot-table2')
        if not table:
            return None
        
        data = {"Ticker": ticker.upper()}
        target_metrics = [
            "Market Cap", "Sales", "Income", "P/E", "Forward P/E", 
            "PEG", "P/S", "EPS next 5Y", "Oper. Margin", "EPS Q/Q", "Sales Q/Q"
        ]
        
        cells = table.find_all('td')
        temp_dict = {}
        for i in range(0, len(cells), 2):
            label = cells[i].text.strip()
            value = cells[i+1].text.strip()
            temp_dict[label] = value
            
        for metric in target_metrics:
            data[metric] = format_to_one_decimal(temp_dict.get(metric, "-"))
                
        return data
    except Exception:
        return None

# 시가총액 정렬용 파서
def parse_market_cap(val):
    if val == '-' or not val: return 0
    val = val.replace(',', '')
    multiplier = 1
    if 'T' in val: multiplier = 1e12
    elif 'B' in val: multiplier = 1e9
    elif 'M' in val: multiplier = 1e6
    try:
        return float(''.join(c for c in val if c.isdigit() or c == '.')) * multiplier
    except: return 0

# UI 구성
st.title("📊 Tech Stock Benchmark Comparison")

user_ticker = st.text_input("비교할 종목 티커를 입력하세요:", "").upper()

benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]
if user_ticker and user_ticker not in benchmarks:
    benchmarks.append(user_ticker)

if user_ticker:
    with st.spinner('데이터를 불러오는 중...'):
        all_data = []
        for t in benchmarks:
            res = get_finviz_data(t)
            if res: all_data.append(res)
            time.sleep(0.05)

        if all_data:
            df = pd.DataFrame(all_data)
            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])

            # 컬럼 설정 (오른쪽 정렬)
            cols = df.columns.tolist()
            column_config = {col: st.column_config.Column(alignment="right") for col in cols if col != "Ticker"}

            # 스타일링 (입력 종목 하이라이트)
            def highlight_inserted(row):
                if row.Ticker == user_ticker:
                    return ['background-color: #3e4a5b; color: white'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_inserted, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            st.markdown("---")
            
            # 차트 영역 배치
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader(f"📈 {user_ticker} Monthly Price Chart")
                price_chart_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=c&ta=0&p=m&s=l"
                st.image(price_chart_url, use_container_width=True)
            
            with col2:
                st.subheader(f"📊 {user_ticker} Fundamental Charts (Quarterly)")
                # Finviz의 펀더멘탈 차트 URL 구조 활용
                # i=eps (GAAP EPS), i=sales (Sales), i=shares (Shares Outstanding)
                base_f_url = f"https://finviz.com/chart.ashx?t={user_ticker}&ty=q&s=m"
                
                st.image(f"{base_f_url}&i=eps", caption="GAAP EPS", use_container_width=True)
                st.image(f"{base_f_url}&i=sales", caption="Sales", use_container_width=True)
                st.image(f"{base_f_url}&i=shares", caption="Shares Outstanding", use_container_width=True)
            
            st.markdown(f"---")
            st.markdown(f"🔗 [Finviz에서 {user_ticker} 상세 정보 보기](https://finviz.com/quote.ashx?t={user_ticker})")
        else:
            st.error("데이터를 가져오지 못했습니다. 티커를 확인해 주세요.")
