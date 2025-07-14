import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- Configure layout to use full width ---
st.set_page_config(layout="wide")

# --- Optional CSS for styling ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    .dataframe th, .dataframe td {
        text-align: center !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Load SRV Data from CSV ---
@st.cache_data
def load_srv_data():
    df = pd.read_csv("reservoir_data.csv")
    return df.set_index("SRV Name").to_dict(orient="index")

srv_data = load_srv_data()

# --- App Title ---
st.title("🚰 SRV Retention Time Calculator")

# --- Side-by-side layout ---
col_input, col_output = st.columns(2)

# --- Left Column: Inputs ---
with col_input:
    selected_srv = st.selectbox("Select Reservoir", options=list(srv_data.keys()))
    srv_info = srv_data[selected_srv]

    st.subheader("Reservoir Information")
    st.write(f"**Volume per Meter Depth:** {srv_info['Volume Per Meter']} m³/m")
    st.write(f"**Operating Capacity:** {srv_info['Operating Capacity']} m³")
    st.write(f"**Minimum Draw Down Level:** {srv_info['Minimum Draw Down']} m")

    current_level = st.number_input("Current Level (m)", min_value=0.0, max_value=10.0, value=0.98, step=0.01)
    current_volume = current_level * srv_info['Volume Per Meter']
    st.write(f"**Calculated Current Volume:** {current_volume:.2f} m³")

    st.subheader("Calculation Start Time")
    start_time_str = st.text_input("Enter Start Time (HH:MM, 24hr)", value="12:00")
    try:
        today = pd.Timestamp.now().normalize()
        start_time = datetime.strptime(start_time_str, "%H:%M")
        start_datetime = pd.Timestamp(today.year, today.month, today.day, start_time.hour, start_time.minute)
    except:
        st.error("Please enter a valid start time in HH:MM format.")
        st.stop()

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
    flow_values = [float(val.strip()) for val in flow_values if val.strip() != ""]
    freq = freq_options[freq_label]
    timestamps = pd.date_range(start=start_dt, periods=len(flow_values), freq=freq)
    return pd.DataFrame({"Flow": flow_values}, index=timestamps)

# --- Right Column: Output ---
with col_output:
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

        # Filter rows with actual flow
        non_zero_rows = (df['Inlet Flow'] != 0) | (df['Outlet Flow'] != 0)
        df_trimmed = df[non_zero_rows]

        # Table highlighting
        def highlight_low_levels(s):
            drawdown = srv_info['Minimum Draw Down']
            return ['background-color: #ffdddd' if v < drawdown else '' for v in s]

        st.subheader("Predicted Reservoir Levels (Hourly)")
        df_display = df_trimmed[['Inlet Flow', 'Outlet Flow', 'Level (m)', 'Level (%)']].round(2)
        styled_table = df_display.style.apply(highlight_low_levels, subset=['Level (m)'])
        st.dataframe(styled_table)


        # Plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_trimmed.index,
            y=df_trimmed['Level (m)'],
            mode='lines+markers',
            name='Reservoir Level (m)',
            line=dict(color='blue', width=3),
            marker=dict(size=6)
        ))

        operating_level = srv_info['Operating Capacity'] / srv_info['Volume Per Meter']
        min_drawdown = srv_info['Minimum Draw Down']

        fig.add_trace(go.Scatter(
            x=df_trimmed.index,
            y=[operating_level] * len(df_trimmed),
            mode='lines',
            name='Operating Capacity',
            line=dict(color='red', dash='dash')
        ))

        fig.add_trace(go.Scatter(
            x=df_trimmed.index,
            y=[min_drawdown] * len(df_trimmed),
            mode='lines',
            name='Minimum Draw Down Level',
            line=dict(color='orange', dash='dot')
        ))

        fig.add_shape(
            type="rect",
            xref="x", yref="y",
            x0=df_trimmed.index[0],
            x1=df_trimmed.index[-1],
            y0=0,
            y1=min_drawdown,
            fillcolor="rgba(255, 200, 200, 0.3)",
            line=dict(width=0),
            layer="below"
        )

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
