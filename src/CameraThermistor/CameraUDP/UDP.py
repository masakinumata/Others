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
    sock.settimeout(0.1)
    return sock

if "log_path" not in st.session_state:
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
    st.session_state.log_path = os.path.join(LOG_DIR, f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

st.set_page_config(page_title="Ultra Stable Telemetry", layout="wide")

if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Time", "BME_T", "Hum", "Pres", "Th1", "Th2", "Event"])
if "event_flag" not in st.session_state:
    st.session_state.event_flag = ""

# --- 1. サイドバー (固定要素) ---
st.sidebar.title("🛠️ Lab Control")
st.sidebar.caption(f"Saving to: {st.session_state.log_path}")

st.sidebar.subheader("Annotation")
cols = st.sidebar.columns(2)
# ボタンを押すとStreamlitが自動でスクリプトを再実行するので st.rerun() は不要
if cols[0].button("🔥 Heater"): st.session_state.event_flag = "HEATER"
if cols[1].button("❄️ Cooler"): st.session_state.event_flag = "COOLER"
if st.sidebar.button("⏹️ Reset Event"): st.session_state.event_flag = ""

st.sidebar.info(f"Active Event: **{st.session_state.event_flag if st.session_state.event_flag else 'NONE'}**")

# ダウンロードボタンもサイドバーに配置（データがある場合のみ）
csv_data = st.session_state.df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Download CSV Now", data=csv_data, file_name="live_data.csv")

# --- 2. メイン UI 構造の定義 (ここがチラつき防止のキモ) ---
st.title("🔬 Advanced Experiment Monitor")
alert_area = st.empty()

# メトリクス用プレースホルダ
m_cols = st.columns(6)
m_placeholders = [c.empty() for c in m_cols]

st.divider()

# タブの作成と、タブ内プレースホルダの確保
tab_chart, tab_stats, tab_log = st.tabs(["📈 Live Graphs", "📊 Statistics", "📜 Event Log"])
with tab_chart:
    chart_t_place = st.empty()
    chart_p_place = st.empty()
with tab_stats:
    stats_place = st.empty()
with tab_log:
    log_table_place = st.empty()

# --- 3. データ受信・更新ループ ---
sock = get_udp_socket()

while True:
    try:
        data, addr = sock.recvfrom(1024)
        raw = data.decode("utf-8").split(",")
        vals = [float(x) for x in raw] # BME_T, Hum, Pres, Th1, Th2
        now = datetime.now().strftime("%H:%M:%S")

        new_row = {
            "Time": now, "BME_T": vals[0], "Hum": vals[1], "Pres": vals[2],
            "Th1": vals[3], "Th2": vals[4], "Event": st.session_state.event_flag
        }
        
        # データの蓄積
        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])]).tail(200)
        df = st.session_state.df

        # --- 部分更新 (チラつかない書き換え) ---
        # アラート
        if max(vals[3], vals[4]) > THRESHOLD_TEMP:
            alert_area.error(f"⚠️ WARNING: High Temperature! (Th1:{vals[3]}°C, Th2:{vals[4]}°C)")
        else:
            alert_area.empty()

        # メトリクス
        m_placeholders[0].metric("Th 1", f"{vals[3]}°C")
        m_placeholders[1].metric("Th 2", f"{vals[4]}°C")
        m_placeholders[2].metric("ΔT", f"{round(abs(vals[3]-vals[4]), 2)}°C")
        m_placeholders[3].metric("BME T", f"{vals[0]}°C")
        m_placeholders[4].metric("Humidity", f"{vals[1]}%")
        m_placeholders[5].metric("Pressure", f"{vals[2]}hPa")

        # グラフ
        chart_t_place.line_chart(df.set_index("Time")[["BME_T", "Th1", "Th2"]])
        chart_p_place.line_chart(df.set_index("Time")[["Hum", "Pres"]])

        # 統計 (平均・最大・最小・標準偏差)
        stats_df = df[["BME_T", "Th1", "Th2"]].astype(float).describe().T[["mean", "max", "min", "std"]]
        stats_place.dataframe(stats_df, use_container_width=True)

        # イベントログ
        events_only = df[df["Event"] != ""][["Time", "Event", "Th1", "Th2"]]
        log_table_place.table(events_only.tail(10))

        # CSV保存
        pd.DataFrame([new_row]).to_csv(st.session_state.log_path, mode='a', index=False, header=not os.path.exists(st.session_state.log_path))

    except socket.timeout:
        # rerun()を削除！ これで待機中のチラつきが消えます
        pass
    except Exception as e:
        st.error(f"Error: {e}")
    
    time.sleep(0.01)