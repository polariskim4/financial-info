import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from io import BytesIO

# 페이지 설정
st.set_page_config(page_title="Finviz Stock Comparison", layout="wide")

# 공통 헤더 설정 (이미지 및 데이터 크롤링용)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finviz.com/'
}

# 1. 이미지를 바이트로 가져오는 함수 (차트 깨짐 방지 핵심)
def get_image_bytes(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content)
        return None
    except Exception:
        return None

# 2. 숫자를 소수점 한자리로 포맷팅
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

# 3. Finviz 데이터 스크래핑
@st.cache_data(ttl=3600)
def get_finviz_data(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
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

user_ticker = st.text_input("비교할 종목 티커를 입력하세요 (예: NVDA, TSLA):", "").upper()

benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]
if user_ticker and user_ticker not in benchmarks:
    benchmarks.append(user_ticker)

if user_ticker:
    with st.spinner('Finviz 데이터를 동기화 중입니다...'):
        all_data = []
        for t in benchmarks:
            res = get_finviz_data(t)
            if res: all_data.append(res)
            time.sleep(0.1)
            
        if all_data:
            df = pd.DataFrame(all_data)
            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])

            # 표 설정
            column_config = {col: st.column_config.Column(alignment="right") for col in df.columns if col != "Ticker"}

            def highlight_row(row):
                if row.Ticker == user_ticker:
                    return ['background-color: #3e4a5b; color: white'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_row, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            st.markdown("---")
            
            # 차트 영역
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader(f"📈 {user_ticker} Monthly Price Chart")
                # 월봉 차트 URL (이미지 서버 직접 호출)
                monthly_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=c&ta=0&p=m&s=l"
                img_data = get_image_bytes(monthly_url)
                if img_data:
                    st.image(img_data, use_container_width=True)
                else:
                    st.warning("월봉 차트를 불러올 수 없습니다.")
            
            with col2:
                st.subheader(f"📊 {user_ticker} Fundamentals (Quarterly)")
                # Finviz의 바 차트용 파라미터 적용
                base_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=q&ta=0&p=m&s=l"
                
                # GAAP EPS, Sales, Shares Outstanding 순서대로 시도
                metrics = [("eps", "GAAP EPS"), ("sales", "Sales"), ("shares", "Shares Outstanding")]
                
                for m_code, m_name in metrics:
                    chart_img = get_image_bytes(f"{base_url}&i={m_code}")
                    if chart_img:
                        st.image(chart_img, caption=m_name, use_container_width=True)
                    else:
                        st.write(f"{m_name} 데이터를 불러올 수 없습니다.")

            st.markdown(f"---")
            st.markdown(f"🔗 [Finviz {user_ticker} 바로가기](https://finviz.com/quote.ashx?t={user_ticker})")
        else:
            st.error("데이터 로드 실패. 티커를 확인해주세요.")
