import streamlit as st
import pandas as pd
import socket
import time
from datetime import datetime
import os

# --- 基本設定 ---
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
LOG_DIR = r"C:\Users\numat\Desktop\CameraLog"
THRESHOLD_TEMP = 50.0

@st.cache_resource
def get_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.5) # 少し長めに待機して安定性を確保
    return sock

if "log_path" not in st.session_state:
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
    st.session_state.log_path = os.path.join(LOG_DIR, f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

st.set_page_config(page_title="Reliable Telemetry Monitor", layout="wide")

# セッション状態の管理
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Time", "BME_T", "Hum", "Pres", "Th1", "Th2", "Event"])
if "event_flag" not in st.session_state:
    st.session_state.event_flag = ""
if "packet_count" not in st.session_state:
    st.session_state.packet_count = 0
if "last_seen" not in st.session_state:
    st.session_state.last_seen = 0

# --- 1. サイドバー (Control Panel) ---
st.sidebar.title("🛠️ Lab Control")
st.sidebar.caption(f"Saving to: {st.session_state.log_path}")

# 通信状態の表示（サイドバー上部）
status_place = st.sidebar.empty()

st.sidebar.subheader("Annotation")
cols = st.sidebar.columns(2)
if cols[0].button("🔥 Heater"): st.session_state.event_flag = "HEATER"
if cols[1].button("❄️ Cooler"): st.session_state.event_flag = "COOLER"
if st.sidebar.button("⏹️ Reset Event"): st.session_state.event_flag = ""

st.sidebar.info(f"Active Event: **{st.session_state.event_flag if st.session_state.event_flag else 'NONE'}**")

# ダウンロードボタン
csv_data = st.session_state.df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Download CSV Now", data=csv_data, file_name="live_data.csv")

# --- 2. メイン UI 構造 ---
st.title("🔬 Advanced Experiment Monitor")
alert_area = st.empty()

# メトリクス用プレースホルダ
m_cols = st.columns(6)
m_placeholders = [c.empty() for c in m_cols]

st.divider()

# タブの作成
tab_chart, tab_stats, tab_log = st.tabs(["📈 Live Graphs", "📊 Statistics", "📜 Event Log"])

with tab_chart:
    st.subheader("Temperature Trend (°C)")
    chart_t_place = st.empty()
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Humidity (%)")
        chart_h_place = st.empty()
    with col_b:
        st.subheader("Pressure (hPa)")
        chart_p_place = st.empty()

with tab_stats:
    stats_place = st.empty()

with tab_log:
    log_table_place = st.empty()

# --- 3. データ受信・更新ループ ---
sock = get_udp_socket()

while True:
    current_time = time.time()
    
    try:
        data, addr = sock.recvfrom(1024)
        raw = data.decode("utf-8").split(",")
        vals = [float(x) for x in raw] 
        now_str = datetime.now().strftime("%H:%M:%S")

        # 状態更新
        st.session_state.packet_count += 1
        st.session_state.last_seen = current_time

        new_row = {
            "Time": now_str, "BME_T": vals[0], "Hum": vals[1], "Pres": vals[2],
            "Th1": vals[3], "Th2": vals[4], "Event": st.session_state.event_flag
        }
        
        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])]).tail(200)
        df = st.session_state.df

        # --- 通信ステータス表示 ---
        status_place.success(f"● ONLINE | Packets: {st.session_state.packet_count}")

        # --- メトリクス更新 ---
        m_placeholders[0].metric("Th 1", f"{vals[3]}°C")
        m_placeholders[1].metric("Th 2", f"{vals[4]}°C")
        m_placeholders[2].metric("ΔT", f"{round(abs(vals[3]-vals[4]), 2)}°C")
        m_placeholders[3].metric("BME T", f"{vals[0]}°C")
        m_placeholders[4].metric("Humidity", f"{vals[1]}%")
        m_placeholders[5].metric("Pressure", f"{vals[2]}hPa")

        # --- グラフ更新 (3つのグラフを個別に更新) ---
        chart_t_place.line_chart(df.set_index("Time")[["BME_T", "Th1", "Th2"]])
        chart_h_place.line_chart(df.set_index("Time")[["Hum"]], color="#29b5e8") # 青系
        chart_p_place.line_chart(df.set_index("Time")[["Pres"]], color="#ffaa00") # オレンジ系

        # 統計・ログの更新
        stats_place.dataframe(df[["BME_T", "Th1", "Th2"]].astype(float).describe().T[["mean", "max", "min", "std"]], use_container_width=True)
        log_table_place.table(df[df["Event"] != ""][["Time", "Event", "Th1", "Th2"]].tail(10))

        # CSV保存
        pd.DataFrame([new_row]).to_csv(st.session_state.log_path, mode='a', index=False, header=not os.path.exists(st.session_state.log_path))

    except socket.timeout:
        # 通信途絶の判定 (2秒以上届かない場合)
        if current_time - st.session_state.last_seen > 2.0:
            status_place.error("● OFFLINE | Disconnected")
        pass
    
    time.sleep(0.01)