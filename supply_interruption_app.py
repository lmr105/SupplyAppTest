import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- Reservoir Data ---
srv_data = {
    "Coed Talog": {
        "volume_per_meter": 281,
        "operating_capacity": 561,
    }
}

# --- App Title ---
st.title("🚰 SRV Retention Time Calculator")

# --- Select Reservoir ---
selected_srv = st.selectbox("Select Reservoir", options=list(srv_data.keys()))
srv_info = srv_data[selected_srv]

st.subheader("Reservoir Information")
st.write(f"**Volume per Meter Depth:** {srv_info['volume_per_meter']} m³/m")
st.write(f"**Operating Capacity:** {srv_info['operating_capacity']} m³")

# --- Current Level Input ---
current_level = st.number_input("Current Level (m)", min_value=0.0, max_value=10.0, value=0.98, step=0.01)
current_volume = current_level * srv_info['volume_per_meter']
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

# --- Helper Function to Generate Timestamped Flow DataFrame ---
def generate_flow_df(flow_text, freq_label, start_dt):
    flow_values = flow_text.strip().splitlines()
    flow_values = [float(val.strip()) for val in flow_values if val.strip() != ""]
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

    # Create 24-hour index
    hourly_index = pd.date_range(start=start_datetime.floor("H"), periods=24, freq="H")
    df = pd.DataFrame(index=hourly_index)

    # Resample to hourly and align with main index
    df['Inlet Flow'] = df_inlet['Flow'].resample("H").mean().reindex(df.index, method="nearest", tolerance=pd.Timedelta("30min")).fillna(0)
    df['Outlet Flow'] = df_outlet['Flow'].resample("H").mean().reindex(df.index, method="nearest", tolerance=pd.Timedelta("30min")).fillna(0)

    # Calculate retention metrics
    df['Net Flow (m³/hr)'] = df['Inlet Flow'] - df['Outlet Flow']
    df['Volume (m³)'] = current_volume + df['Net Flow (m³/hr)'].cumsum()
    df['Level (m)'] = df['Volume (m³)'] / srv_info['volume_per_meter']
    df['Level (%)'] = (df['Volume (m³)'] / srv_info['operating_capacity']) * 100

    # Trim to rows where either inlet or outlet flow is present
    non_zero_rows = (df['Inlet Flow'] != 0) | (df['Outlet Flow'] != 0)
    df_trimmed = df[non_zero_rows]

    # --- Output Table ---
    st.subheader("Predicted Reservoir Levels (Hourly)")
    st.dataframe(df_trimmed[['Inlet Flow', 'Outlet Flow', 'Level (m)', 'Level (%)']].round(2))

    # --- Interactive Plotly Chart ---
    fig = go.Figure()

    # Reservoir level line
    fig.add_trace(go.Scatter(
        x=df_trimmed.index,
        y=df_trimmed['Level (m)'],
        mode='lines+markers',
        name='Reservoir Level (m)',
        line=dict(color='blue', width=3),
        marker=dict(size=6)
    ))

    # Max capacity line
    max_level = srv_info['operating_capacity'] / srv_info['volume_per_meter']
    fig.add_trace(go.Scatter(
        x=df_trimmed.index,
        y=[max_level] * len(df_trimmed),
        mode='lines',
        name='Max Capacity',
        line=dict(color='red', dash='dash')
    ))

    fig.update_layout(
        title="Reservoir Level Over Time",
        xaxis_title="Time",
        yaxis_title="Level (m)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=40, b=40),
        height=400,
        template='plotly_white'
    )

    st.plotly_chart(fig, use_container_width=True)

    st.success("Calculation complete!")
