import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IDX Emiten", layout="wide")

st.title("📊 IDX Emiten Dashboard")
st.caption("Safe mode (tanpa scraping IDX langsung)")

# =========================
# DATA STATIC (AMAN)
# =========================
@st.cache_data
def load_data():
    # sumber alternatif (CSV publik GitHub - stabil)
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
    
    # NOTE: ini contoh fallback (bukan IDX asli)
    # nanti bisa diganti dengan dataset IDX kalau kamu punya

    df = pd.read_csv(url)

    # rename biar mirip saham
    df = df.rename(columns={
        "Symbol": "Symbol",
        "Name": "Name"
    })

    return df


df = load_data()

# =========================
# METRICS
# =========================
col1, col2 = st.columns(2)

with col1:
    st.metric("Total Data", len(df))

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

# =========================
# TABLE
# =========================
st.subheader("📋 Data")

st.dataframe(df, use_container_width=True, height=600)

# =========================
# DOWNLOAD
# =========================
st.download_button(
    "⬇️ Download CSV",
    df.to_csv(index=False),
    "data.csv",
    "text/csv"
)

# =========================
# REFRESH
# =========================
if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
