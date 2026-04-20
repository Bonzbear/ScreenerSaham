import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ===== CONFIG =====
st.set_page_config(
    page_title="IDX Market Dashboard",
    layout="wide"
)

st.title("📊 IDX Market Data (All Stocks)")
st.caption("Data delay ±10–15 menit | Source: IDX")

# ===== FETCHER =====
@st.cache_data(ttl=300)  # cache 5 menit
def fetch_idx_data():
    url = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
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

        df = pd.DataFrame(parsed)

        return df

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


# ===== LOAD DATA =====
df = fetch_idx_data()

# ===== INFO HEADER =====
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Emiten", len(df))

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

with col3:
    st.metric("Data Source", "IDX")

# ===== DISPLAY TABLE =====
st.subheader("📋 Seluruh Saham")

if not df.empty:
    st.dataframe(
        df,
        use_container_width=True,
        height=600
    )
else:
    st.warning("Data tidak tersedia")

# ===== DOWNLOAD =====
st.download_button(
    label="⬇️ Download CSV",
    data=df.to_csv(index=False),
    file_name="idx_all_stocks.csv",
    mime="text/csv"
)

# ===== AUTO REFRESH BUTTON =====
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
