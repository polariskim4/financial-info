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
@st.cache_data(ttl=3600)  # 1시간 동안 캐시 유지
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
        # Finviz의 데이터는 'snapshot-table2' 클래스의 테이블에 위치함
        table = soup.find('table', class_='snapshot-table2')
        if not table:
            return None
        
        data = {"Ticker": ticker.upper()}
        
        # 종목명(Company Name) 추출
        company_name = "-"
        title_table = soup.find('table', class_='fullview-title')
        if title_table:
            name_link = title_table.find('a', class_='tab-link')
            if name_link:
                company_name = name_link.text.strip()
        data["Company"] = company_name
        
        # 찾고자 하는 항목 매핑
        target_metrics = {
            "Market Cap": "Market Cap",
            "Sales": "Sales",
            "Income": "Income",
            "P/E": "P/E",
            "Forward P/E": "Forward P/E",
            "PEG": "PEG",
            "P/S": "P/S",
            "EPS next 5Y": "EPS next 5Y",
            "Oper. Margin": "Oper. Margin",
            "EPS Q/Q": "EPS Q/Q",
            "Sales Q/Q": "Sales Q/Q"
        }
        
        cells = table.find_all('td')
        for i in range(0, len(cells), 2):
            label = cells[i].text.strip()
            value = cells[i+1].text.strip()
            if label in target_metrics:
                data[label] = format_to_one_decimal(value)
                
        return data
    except Exception as e:
        return None

# 2. 시가총액 문자열을 숫자로 변환 (정렬용)
def parse_market_cap(val):
    if val == '-' or not val: return 0
    val = val.replace(',', '')
    multiplier = 1
    if 'T' in val: multiplier = 1e12
    elif 'B' in val: multiplier = 1e9
    elif 'M' in val: multiplier = 1e6
    
    try:
        return float(''.join(c for c in val if c.isdigit() or c == '.')) * multiplier
    except:
        return 0

# UI 구성
st.title("📊 Tech Stock Benchmark Comparison")
st.markdown("Finviz 데이터를 바탕으로 주요 테크 종목과 입력 종목을 비교합니다.")

# 입력창
user_ticker = st.text_input("비교할 종목 티커를 입력하세요 (예: TSLA, AAPL):", "").upper()

# 벤치마크 리스트
benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]
if user_ticker and user_ticker not in benchmarks:
    benchmarks.append(user_ticker)

if st.button("데이터 불러오기") or user_ticker:
    with st.spinner('Finviz에서 데이터를 가져오는 중...'):
        all_data = []
        for t in benchmarks:
            res = get_finviz_data(t)
            if res:
                all_data.append(res)
            time.sleep(0.2) # 과도한 요청 방지

        if all_data:
            df = pd.DataFrame(all_data)
            
            # 컬럼 순서 재배치
            columns_order = [
                "Ticker", "Company", "Market Cap", "Sales", "Income", 
                "P/E", "Forward P/E", "PEG", "P/S", "EPS next 5Y", 
                "Oper. Margin", "EPS Q/Q", "Sales Q/Q"
            ]
            # 존재하는 컬럼만 선택 (만약의 에러 방지)
            df = df[[c for c in columns_order if c in df.columns]]

            # 시가총액 기준 정렬을 위한 임시 컬럼 생성
            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])
            
            # 스타일링 함수: 입력한 종목만 강조
            def highlight_inserted(row):
                if row.Ticker == user_ticker:
                    return ['background-color: #2c3e50; color: white'] * len(row)
                return [''] * len(row)

            # 데이터프레임 표시
            st.dataframe(
                df.style.apply(highlight_inserted, axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # Monthly 차트 디스플레이
            if user_ticker:
                st.markdown(f"### 📈 {user_ticker} Monthly Chart")
                chart_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=c&ta=0&p=m&s=l"
                st.image(chart_url, use_container_width=True)
            
            # 하단 링크
            if user_ticker:
                st.markdown(f"---")
                st.markdown(f"🔗 [Finviz에서 {user_ticker} 상세 정보 보기](https://finviz.com/quote.ashx?t={user_ticker})")
        else:
            st.error("데이터를 불러오지 못했습니다. 티커가 정확한지 확인해주세요.")
