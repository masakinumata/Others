import streamlit as st
import pandas as pd
import socket
import time
from datetime import datetime, timedelta
import os

# --- 基本設定 ---
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
LOG_DIR = r"C:\Users\numat\Desktop\CameraLog"

@st.cache_resource
def get_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.1)
    return sock

if "log_path" not in st.session_state:
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
    st.session_state.log_path = os.path.join(LOG_DIR, f"freezer_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

st.set_page_config(page_title="Freezer Test Monitor", layout="wide")

# セッション状態の初期化
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Time", "Elapsed", "BME_T", "Hum", "Pres", "Th1", "Th2", "Event"])
if "event_flag" not in st.session_state:
    st.session_state.event_flag = ""
if "start_time" not in st.session_state:
    st.session_state.start_time = None 
if "packet_count" not in st.session_state:
    st.session_state.packet_count = 0
if "last_seen" not in st.session_state:
    st.session_state.last_seen = 0

# --- サイドバー (試験管理) ---
st.sidebar.title("❄️ Freezer Test Control")

# 1. 経過時間タイマー
st.sidebar.subheader("Test Timer")
if st.sidebar.button("🚀 Start Test (Put in Freezer)"):
    st.session_state.start_time = time.time()
    st.session_state.event_flag = "START_TEST"

if st.session_state.start_time:
    elapsed_sec = int(time.time() - st.session_state.start_time)
    elapsed_str = str(timedelta(seconds=elapsed_sec))
    st.sidebar.metric("Elapsed Time", elapsed_str)
    if st.sidebar.button("Reset Timer"):
        st.session_state.start_time = None
else:
    st.sidebar.write("Timer not started")

# 2. イベントラベル
st.sidebar.subheader("Event Labeling")
e_col1, e_col2 = st.sidebar.columns(2)
if e_col1.button("📷 Cam ON"): st.session_state.event_flag = "CAM_ON"
if e_col2.button("🚫 Cam OFF"): st.session_state.event_flag = "CAM_OFF"
if e_col1.button("🚪 Door Open"): st.session_state.event_flag = "DOOR_OPEN"
if e_col2.button("🔒 Door Close"): st.session_state.event_flag = "DOOR_CLOSE"
if st.sidebar.button("📦 Take Out"): st.session_state.event_flag = "TAKE_OUT"
if st.sidebar.button("⏹️ Clear Label"): st.session_state.event_flag = ""

st.sidebar.info(f"Active Label: **{st.session_state.event_flag if st.session_state.event_flag else 'NONE'}**")

# --- メイン UI ---
st.title("🔬 Camera Low-Temp Reliability Test")
status_place = st.empty()

m_cols = st.columns(6)
m_placeholders = [c.empty() for c in m_cols]

st.divider()

tab_chart, tab_stats, tab_log = st.tabs(["📈 Graphs", "📊 Stats", "📜 Log"])

with tab_chart:
    st.subheader("Temperature Trend (°C)")
    chart_t = st.empty()
    col_a, col_b = st.columns(2)
    chart_h = col_a.empty()
    chart_p = col_b.empty()

with tab_stats: stats_place = st.empty()
with tab_log: log_table_place = st.empty()

# --- データ受信ループ ---
sock = get_udp_socket()

while True:
    current_time = time.time()
    try:
        data, addr = sock.recvfrom(1024)
        raw = data.decode("utf-8").split(",")
        vals = [float(x) for x in raw] 
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # 経過時間の算出
        if st.session_state.start_time:
            elapsed_val = str(timedelta(seconds=int(current_time - st.session_state.start_time)))
        else:
            elapsed_val = "0:00:00"

        st.session_state.packet_count += 1
        st.session_state.last_seen = current_time

        new_row = {
            "Time": now_str, "Elapsed": elapsed_val,
            "BME_T": vals[0], "Hum": vals[1], "Pres": vals[2],
            "Th1": vals[3], "Th2": vals[4], "Event": st.session_state.event_flag
        }
        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])]).tail(300)
        df = st.session_state.df

        # 表示更新
        if current_time - st.session_state.last_seen < 1.0:
            status_place.success(f"● ONLINE | Packets: {st.session_state.packet_count}")
        
        m_placeholders[0].metric("Th 1 (Camera1)", f"{vals[3]}°C")
        m_placeholders[1].metric("Th 2 (Camera2)", f"{vals[4]}°C")
        m_placeholders[2].metric("Elapsed", elapsed_val)
        m_placeholders[3].metric("BME Temp", f"{vals[0]}°C")
        m_placeholders[4].metric("Humidity", f"{vals[1]}%")
        m_placeholders[5].metric("Pressure", f"{vals[2]}hPa")

        # グラフ (経過時間をX軸に使用)
        chart_t.line_chart(df.set_index("Elapsed")[["BME_T", "Th1", "Th2"]])
        chart_h.line_chart(df.set_index("Elapsed")[["Hum"]], color="#29b5e8")
        chart_p.line_chart(df.set_index("Elapsed")[["Pres"]], color="#ffaa00")

        stats_place.dataframe(df[["BME_T", "Th1", "Th2"]].astype(float).describe().T[["mean", "max", "min", "std"]], use_container_width=True)
        log_table_place.table(df[df["Event"] != ""][["Elapsed", "Event", "Th1", "Th2"]].tail(10))

        # PermissionError対策
        try:
            pd.DataFrame([new_row]).to_csv(st.session_state.log_path, mode='a', index=False, header=not os.path.exists(st.session_state.log_path))
        except PermissionError:
            pass

    except socket.timeout:
        if current_time - st.session_state.last_seen > 2.0:
            status_place.error("● OFFLINE | Disconnected")
        pass
    
    time.sleep(0.01)