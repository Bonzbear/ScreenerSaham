import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

st.set_page_config(page_title="IDX Emiten", layout="wide")

st.title("📊 IDX Emiten Dashboard")
st.caption("Stable version (no IDX scraping, no urllib error)")

# =========================
# FETCH DATA (SAFE)
# =========================
@st.cache_data(ttl=3600)
def load_idx_data():

    url = "https://raw.githubusercontent.com/selva86/datasets/master/IDX_stocks.csv"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            return None, f"HTTP Error {r.status_code}"

        # convert ke dataframe
        csv_data = StringIO(r.text)
        df = pd.read_csv(csv_data)

        return df, None

    except Exception as e:
        return None, str(e)


df, error = load_idx_data()

# =========================
# METRICS
# =========================
col1, col2 = st.columns(2)

with col1:
    st.metric("Total Emiten", len(df) if df is not None else 0)

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

# =========================
# ERROR HANDLING
# =========================
if error:
    st.error(error)
    st.stop()

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
