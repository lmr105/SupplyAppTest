import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import tempfile
import os
from datetime import datetime

# --- Load SRV Data from CSV ---
@st.cache_data
def load_srv_data():
    df = pd.read_csv("reservoir_data.csv")
    return df.set_index("SRV Name").to_dict(orient="index")

srv_data = load_srv_data()

# --- App Title ---
st.title("🚰 SRV Retention Time Calculator")

# --- Select Reservoir ---
selected_srv = st.selectbox("Select Reservoir", options=list(srv_data.keys()))
srv_info = srv_data[selected_srv]

st.subheader("Reservoir Information")
st.write(f"**Volume per Meter Depth:** {srv_info['Volume Per Meter']} m³/m")
st.write(f"**Operating Capacity:** {srv_info['Operating Capacity']} m³")
st.write(f"**Minimum Draw Down Level:** {srv_info['Minimum Draw Down']} m")

# --- Current Level Input ---
current_level = st.number_input("Current Level (m)", min_value=0.0, max_value=10.0, value=0.98, step=0.01)
current_volume = current_level * srv_info['Volume Per Meter']
st.write(f"**Calculated Current Volume:** {current_volume:.2f} m³")

# --- Start Time Input ---
st.subheader("Calculation Start Time")
start_time_str = st.text_input("Enter Start Time (HH:MM, 24hr)", value="12:00")
try:
    today = pd.Timestamp.now().normalize()
    start_time = datetime.strptime(start_time_str, "%H:%M")
    start_datetime = pd.Timestamp(today.year, today.month, today.day, start_time.hour, start_time.minute)
except:
    st.error("Please enter a valid start time in HH:MM format.")
    st.stop()

# --- Flow Data Frequency and Input ---
st.subheader("Flow Data Input")

freq_options = {
    "15 minute": "15min",
    "30 minute": "30min",
    "60 minute": "60min"
}

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Inlet Flow")
    inlet_freq_label = st.selectbox("Inlet Data Frequency", options=freq_options.keys())
    inlet_data = st.text_area("Enter Inlet Flow Values (m³/hr)", "15\n15\n15\n15")

with col2:
    st.markdown("### Outlet Flow")
    outlet_freq_label = st.selectbox("Outlet Data Frequency", options=freq_options.keys())
    outlet_data = st.text_area("Enter Outlet Flow Values (m³/hr)", "20\n18")

# --- Helper Function ---
def generate_flow_df(flow_text, freq_label, start_dt):
    flow_values = flow_text.strip().splitlines()
    flow_values = [float(val.strip()) for val in flow_values if val.strip()]
    freq = freq_options[freq_label]
    timestamps = pd.date_range(start=start_dt, periods=len(flow_values), freq=freq)
    return pd.DataFrame({"Flow": flow_values}, index=timestamps)

# --- Run Calculation ---
if st.button("Calculate Retention"):
    try:
        df_inlet = generate_flow_df(inlet_data, inlet_freq_label, start_datetime)
        df_outlet = generate_flow_df(outlet_data, outlet_freq_label, start_datetime)
    except Exception as e:
        st.error(f"Error parsing flow data: {e}")
        st.stop()

    hourly_index = pd.date_range(start=start_datetime.floor("H"), periods=24, freq="H")
    df = pd.DataFrame(index=hourly_index)

    df['Inlet Flow'] = df_inlet['Flow'].resample("H").mean().reindex(df.index, method="nearest", tolerance=pd.Timedelta("30min")).fillna(0)
    df['Outlet Flow'] = df_outlet['Flow'].resample("H").mean().reindex(df.index, method="nearest", tolerance=pd.Timedelta("30min")).fillna(0)

    df['Net Flow (m³/hr)'] = df['Inlet Flow'] - df['Outlet Flow']
    df['Volume (m³)'] = current_volume + df['Net Flow (m³/hr)'].cumsum()
    df['Level (m)'] = df['Volume (m³)'] / srv_info['Volume Per Meter']
    df['Level (%)'] = (df['Volume (m³)'] / srv_info['Operating Capacity']) * 100
    df_trimmed = df[(df['Inlet Flow'] != 0) | (df['Outlet Flow'] != 0)]

    st.session_state['retention_df'] = df_trimmed
    st.session_state['start_datetime'] = start_datetime
    st.session_state['current_level'] = current_level
    st.session_state['selected_srv'] = selected_srv
    st.session_state['srv_info'] = srv_info

# --- Display if results exist ---
if 'retention_df' in st.session_state:
    df_trimmed = st.session_state['retention_df']
    df_display = df_trimmed[['Inlet Flow', 'Outlet Flow', 'Level (m)', 'Level (%)']].round(2)

    def highlight_low_levels(s):
        drawdown = st.session_state['srv_info']['Minimum Draw Down']
        return ['background-color: #ffdddd' if v < drawdown else '' for v in s]

    st.subheader("Predicted Reservoir Levels (Hourly)")
    st.dataframe(df_display.style.apply(highlight_low_levels, subset=['Level (m)']))

    # --- PDF Export (Table Only) ---
    if st.button("Download PDF Report"):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "SRV Retention Time Report", ln=1, align="C")
            pdf.set_font("Arial", size=12)

            pdf.cell(0, 10, f"Reservoir: {st.session_state['selected_srv']}", ln=1)
            pdf.cell(0, 10, f"Start Time: {st.session_state['start_datetime'].strftime('%Y-%m-%d %H:%M')}", ln=1)
            pdf.cell(0, 10, f"Current Level: {st.session_state['current_level']:.2f} m", ln=1)
            pdf.cell(0, 10, f"Operating Capacity: {srv_info['Operating Capacity']} m³", ln=1)
            pdf.cell(0, 10, f"Minimum Draw Down Level: {srv_info['Minimum Draw Down']} m", ln=1)

            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "Summary Table (First 10 Rows)", ln=1)
            pdf.set_font("Arial", size=10)
            preview = df_display.head(10)
            for index, row in preview.iterrows():
                time_str = index.strftime('%H:%M')
                line = f"{time_str} | In: {row['Inlet Flow']} | Out: {row['Outlet Flow']} | Level: {row['Level (m)']}m | {row['Level (%)']:.1f}%"
                pdf.cell(0, 8, line, ln=1)

            pdf_path = os.path.join(tmpdir, "retention_report.pdf")
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name="retention_report.pdf", mime="application/pdf")
