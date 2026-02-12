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

# ソケットのキャッシュ（接続維持）
@st.cache_resource
def get_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.1) # タイムアウトを短く設定
    return sock

# ログ保存パスの設定
if "log_path" not in st.session_state:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    filename = f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    st.session_state.log_path = os.path.join(LOG_DIR, filename)

# ページ設定
st.set_page_config(page_title="XIAO Stable Telemetry", layout="wide")

# セッション状態の初期化
if "data_history" not in st.session_state:
    st.session_state.data_history = pd.DataFrame(columns=["Time", "BME_T", "Hum", "Pres", "Th1", "Th2", "Event"])
if "event_flag" not in st.session_state:
    st.session_state.event_flag = ""

# --- サイドバー UI ---
st.sidebar.title("🚀 Control Panel")
st.sidebar.write(f"📁 Saving to: `{st.session_state.log_path}`")

st.sidebar.subheader("Event Markers")
# ボタンが押されるとStreamlitは自動で最初から実行し直すため、rerunは不要
if st.sidebar.button("🔥 Heater ON"): st.session_state.event_flag = "HEATER_ON"
if st.sidebar.button("❄️ Cooler ON"): st.session_state.event_flag = "COOLER_ON"
if st.sidebar.button("🚪 Window Open"): st.session_state.event_flag = "WINDOW_OPEN"
if st.sidebar.button("⏹️ Reset Event"): st.session_state.event_flag = ""

st.sidebar.success(f"Current Event: {st.session_state.event_flag if st.session_state.event_flag else 'None'}")

# --- メイン UI 枠組み（固定部分） ---
st.title("XIAO ESP32-C3 Multi-Sensor Telemetry")

st.subheader("Current Metrics")
row1 = st.columns(3)
row2 = st.columns(3)

# プレースホルダ（中身を書き換えるための空箱）の作成
placeholders = {
    "th1": row1[0].empty(), "th2": row1[1].empty(), "dt": row1[2].empty(),
    "bme_t": row2[0].empty(), "hum": row2[1].empty(), "pres": row2[2].empty(),
    "chart_temp": st.empty(),
    "chart_other": st.empty()
}

# --- データ受信・更新ループ ---
sock = get_udp_socket()

# Streamlitの無限ループ処理
while True:
    try:
        # UDP受信（0.1秒待機）
        data, addr = sock.recvfrom(1024)
        raw = data.decode("utf-8").split(",")
        vals = [float(x) for x in raw]
        now = datetime.now().strftime("%H:%M:%S")

        # データの整理
        new_entry = {
            "Time": now, "BME_T": vals[0], "Hum": vals[1], "Pres": vals[2],
            "Th1": vals[3], "Th2": vals[4], "Event": st.session_state.event_flag
        }

        # 履歴データの更新
        st.session_state.data_history = pd.concat([st.session_state.data_history, pd.DataFrame([new_entry])]).tail(100)

        # 【改善】プレースホルダの中身だけを更新
        placeholders["th1"].metric("Thermistor 1", f"{vals[3]} °C")
        placeholders["th2"].metric("Thermistor 2", f"{vals[4]} °C")
        placeholders["dt"].metric("ΔT (Th1 - Th2)", f"{round(abs(vals[3]-vals[4]), 2)} °C")
        
        placeholders["bme_t"].metric("BME280 Temp", f"{vals[0]} °C")
        placeholders["hum"].metric("Humidity", f"{vals[1]} %")
        placeholders["pres"].metric("Pressure", f"{vals[2]} hPa")

        # グラフの更新（全体を再描画せず上書き）
        placeholders["chart_temp"].line_chart(st.session_state.data_history.set_index("Time")[["BME_T", "Th1", "Th2"]])
        # 下段グラフは表示を整理
        placeholders["chart_other"].line_chart(st.session_state.data_history.set_index("Time")[["Hum", "Pres"]])

        # CSV保存
        df_to_save = pd.DataFrame([new_entry])
        df_to_save.to_csv(st.session_state.log_path, mode='a', index=False, header=not os.path.exists(st.session_state.log_path))

    except socket.timeout:
        # タイムアウト時は何もしない（st.rerun()を削除したことでチラつきが止まる）
        # Streamlitの仕様上、ボタンが押されれば勝手に再起動するので大丈夫です
        pass
    except Exception as e:
        st.error(f"Error: {e}")
    
    # ループ速度を調整（CPU負荷軽減）
    time.sleep(0.01)