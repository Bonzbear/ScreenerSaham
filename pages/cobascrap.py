import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="IDX Emiten Dashboard",
    layout="wide"
)

st.title("📊 IDX Emiten Dashboard")
st.caption("Ambil seluruh emiten | Source: IDX | Safe mode (anti error)")

# =========================
# FETCH FUNCTION (HARDENED)
# =========================
@st.cache_data(ttl=3600)
def fetch_idx_companies():
    url = "https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)

        # ===== CHECK STATUS =====
        if r.status_code != 200:
            return None, f"HTTP Error {r.status_code}"

        # ===== CHECK CONTENT TYPE =====
        content_type = r.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return None, "Response bukan JSON (kemungkinan diblok IDX)"

        # ===== PARSE JSON =====
        try:
            data = r.json()
        except Exception:
            return None, "Gagal decode JSON"

        # ===== VALIDATE STRUCTURE =====
        if "Data" not in data:
            return None, "Format data berubah (tidak ada key 'Data')"

        df = pd.DataFrame(data["Data"])

        return df, None

    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"


# =========================
# LOAD DATA
# =========================
df, error = fetch_idx_companies()

# =========================
# HEADER METRICS
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Emiten", len(df) if df is not None else 0)

with col2:
    st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

with col3:
    st.metric("Status", "OK" if df is not None else "ERROR")

# =========================
# ERROR HANDLING
# =========================
if error:
    st.error(error)
    st.stop()

# =========================
# DISPLAY DATA
# =========================
st.subheader("📋 Daftar Seluruh Emiten")

if df is not None and not df.empty:
    st.dataframe(
        df,
        use_container_width=True,
        height=600
    )
else:
    st.warning("Data kosong")

# =========================
# DOWNLOAD
# =========================
st.download_button(
    label="⬇️ Download CSV",
    data=df.to_csv(index=False),
    file_name="idx_emiten.csv",
    mime="text/csv"
)

# =========================
# REFRESH BUTTON
# =========================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
