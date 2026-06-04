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

# 2. Finviz 데이터 스크래핑 함수 (사용자 확인 결과에 따라 ROIC 직접 참조)
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
        # 테이블의 라벨과 값을 딕셔너리로 저장
        temp_dict = {cells[i].text.strip(): cells[i+1].text.strip() for i in range(0, len(cells), 2)}
        
        data = {"Ticker": ticker.upper()}
        
        # 사용자님께서 확인하신 대로 "ROIC" 라벨을 직접 사용합니다.
        target_metrics = [
            "Market Cap", "Sales", "Income", "P/E", "Forward P/E", 
            "PEG", "P/S", "EPS next 5Y", "Oper. Margin", "ROIC", "EPS Q/Q", "Sales Q/Q"
        ]
            
        for metric in target_metrics:
            raw_val = temp_dict.get(metric, "-")
            data[metric] = format_to_one_decimal(raw_val)
                
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

# --- UI 구성 섹션 ---
st.title("📊 Tech Stock Benchmark Comparison")

# [해결] 고유 key를 추가하여 DuplicateElementId 에러를 방지합니다.
user_ticker = st.text_input(
    "비교할 종목 티커를 입력하세요:", 
    placeholder="예: AAPL, NVDA",
    key="main_stock_input_widget"
).upper()

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
            
            # 컬럼 순서 설정
            ordered_cols = [
                "Ticker", "Market Cap", "Sales", "Income", 
                "P/E", "3yr avg P/E", "Forward P/E", 
                "PEG", "P/S", "EPS next 5Y", 
                "Oper. Margin", "ROIC", "EPS Q/Q", "Sales Q/Q"
            ]
            df = df[[c for c in ordered_cols if c in df.columns]]

            df['cap_value'] = df['Market Cap'].apply(parse_market_cap)
            df = df.sort_values(by='cap_value', ascending=False).drop(columns=['cap_value'])

            # [해결] 최신 Streamlit 문법: width="stretch" 적용
            column_config = {col: st.column_config.Column(alignment="right") for col in df.columns if col != "Ticker"}

            def highlight_inserted(row):
                if row.Ticker == user_ticker:
                    return ['background-color: #3e4a5b; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_inserted, axis=1),
                width="stretch", 
                hide_index=True,
                column_config=column_config
            )
            
            # 차트 섹션
            st.markdown(f"### 📈 {user_ticker} Monthly Chart")
            col1, _ = st.columns([2, 1])
            with col1:
                chart_url = f"https://charts2.finviz.com/chart.ashx?t={user_ticker}&ty=c&ta=0&p=m&s=l"
                st.image(chart_url, width="stretch")
            
            st.markdown(f"---")
            st.caption(f"🔗 [Finviz에서 {user_ticker} 상세 정보 보기](https://finviz.com/quote.ashx?t={user_ticker})")
        else:
            st.error("데이터를 가져오지 못했습니다. 티커가 올바른지 확인해 주세요.")
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
    # 문자열 처리: 콤마와 공백 제거
    num_str = str(val).replace(',', '').strip()
    
    # % 기호나 단위 기호(T, B, M, K) 처리
    if num_str.endswith('%'):
        suffix = '%'
        num_str = num_str[:-1]
    elif len(num_str) > 1 and num_str[-1].upper() in ['T', 'B', 'M', 'K']:
        suffix = num_str[-1].upper()
        num_str = num_str[:-1]
    
    try:
        # 부동소수점으로 변환 후 소수점 한자리 포맷팅
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
            "ROIC": "ROIC", 
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

# --- UI 레이아웃 구성 ---
st.title("📊 Tech Stock Benchmark Comparison")

# [변경사항] 최대 3개까지 입력 가능하도록 가이드 제공 및 콤마 분리 로직
user_input = st.text_input(
    "비교할 종목 티커를 입력하세요 (최대 3개, 콤마로 구분):", 
    placeholder="예: AAPL, NVDA, TSLA",
    key="unique_stock_comparison_key"
).upper()

# 입력된 티커 리스트화 (최대 3개)
user_tickers = [t.strip() for t in user_input.split(",") if t.strip()][:3]

benchmarks = ["NVDA", "GOOG", "MSFT", "META", "NFLX", "ANET", "MRVL", "CRDO", "VRT", "VST", "SOFI", "ORCL"]

# 입력된 티커들을 벤치마크 리스트에 추가 (중복 제거)
for t in user_tickers:
    if t not in benchmarks:
        benchmarks.append(t)

if user_tickers:
    with st.spinner('데이터를 수집하고 분석하는 중...'):
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

            # [변경사항] 입력된 모든 티커를 하이라이트
            def highlight_inserted(row):
                if row.Ticker in user_tickers:
                    return ['background-color: #3e4a5b; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(highlight_inserted, axis=1),
                width="stretch", 
                hide_index=True,
                column_config=column_config
            )
            
            st.markdown("---")
            
            # [변경사항] 하단 차트 섹션 - 입력된 종목 개수만큼 컬럼을 생성하여 차트 표시
            st.subheader("📈 Monthly Charts")
            if len(user_tickers) > 0:
                cols = st.columns(len(user_tickers))
                for i, t in enumerate(user_tickers):
                    with cols[i]:
                        st.markdown(f"#### {t}")
                        chart_url = f"https://charts2.finviz.com/chart.ashx?t={t}&ty=c&ta=0&p=m&s=l"
                        st.image(chart_url, width="stretch")
                        st.caption(f"🔗 [Finviz {t} 상세 정보](https://finviz.com/quote.ashx?t={t})")
            
        else:
            st.error("데이터를 가져오지 못했습니다. 티커가 올바른지 확인해 주세요.")
