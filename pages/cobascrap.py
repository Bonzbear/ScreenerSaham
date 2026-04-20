import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IDX Market", layout="wide")

st.title("📊 IDX Market Data (All Stocks)")
st.caption("Data delay ±10–15 menit | Source: IDX")

# ===== SESSION SETUP (ANTI 403) =====
def create_session():
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.idx.co.id/",
        "Origin": "https://www.idx.co.id",
        "Connection": "keep-alive"
    }

    session.headers.update(headers)

    # 🔥 IMPORTANT: hit homepage dulu (ambil cookies)
    session.get("https://www.idx.co.id/")

    return session


# ===== FETCH DATA =====
@st.cache_data(ttl=300)
def fetch_idx_data():
    session = create_session()

    url = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"

    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()

        json_data = r.json()
        stocks = json_data.get("Data", [])

        parsed = []
        for s in stocks:
            parsed.append({
                "Symbol": s.get("Code"),
                "Name": s.get("Name"),
                "Last": to_float(s.get("Last")),
                "Change": to_float(s.get("Change")),
                "Volume": to_int(s.get("Volume")),
                "Value": to_int(s.get("Value")),
                "Freq": to_int(s.get("Frequency")),
            })

        return pd.DataFrame(parsed)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()


def to_float(val):
    try:
        return float(str(val).replace(",", ""))
    except:
        return None


def to_int(val):
    try:
        return int(str(val).replace(",", ""))
    except:
        return None


# ===== LOAD =====
df = fetch_idx_data()

# ===== HEADER =====
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Emiten", len(df))

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

with col3:
    st.metric("Status", "OK" if not df.empty else "FAILED")

# ===== TABLE =====
st.subheader("📋 Seluruh Saham")

if not df.empty:
    st.dataframe(df, use_container_width=True, height=600)
else:
    st.warning("Data kosong / gagal fetch")

# ===== DOWNLOAD =====
st.download_button(
    label="⬇️ Download CSV",
    data=df.to_csv(index=False),
    file_name="idx_all_stocks.csv",
    mime="text/csv"
)

# ===== REFRESH =====
if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
