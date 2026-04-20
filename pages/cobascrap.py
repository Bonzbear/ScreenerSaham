import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IDX Emiten", layout="wide")

st.title("📊 IDX Emiten Dashboard")
st.caption("Daftar saham Indonesia (IDX) | Tanpa scraping langsung")

# =========================
# DATA IDX (PUBLIC CSV)
# =========================
@st.cache_data
def load_idx_data():
    url = "https://raw.githubusercontent.com/selva86/datasets/master/IDX_stocks.csv"
    
    df = pd.read_csv(url)

    return df

df = load_idx_data()

# =========================
# METRICS
# =========================
col1, col2 = st.columns(2)

with col1:
    st.metric("Total Emiten", len(df))

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

# =========================
# TABLE
# =========================
st.subheader("📋 Daftar Saham Indonesia")

st.dataframe(df, use_container_width=True, height=600)

# =========================
# DOWNLOAD
# =========================
st.download_button(
    "⬇️ Download CSV",
    df.to_csv(index=False),
    "idx_emiten.csv",
    "text/csv"
)

# =========================
# REFRESH
# =========================
if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
