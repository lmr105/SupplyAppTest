import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Reservoir Database (Prototype example)
srv_data = {
    "Coed Talog": {
        "volume_per_meter": 281,
        "operating_capacity": 561,
    }
}

st.title("🚰 SRV Retention Time Calculator")

# Reservoir Selection
selected_srv = st.selectbox("Select Reservoir", options=list(srv_data.keys()))
srv_info = srv_data[selected_srv]

st.subheader("Reservoir Information")
st.write(f"**Volume per Meter Depth:** {srv_info['volume_per_meter']} m³/m")
st.write(f"**Operating Capacity:** {srv_info['operating_capacity']} m³")

# User Input for Current Level
current_level = st.number_input("Current Level (m)", min_value=0.0, max_value=10.0, value=0.98, step=0.01)
current_volume = current_level * srv_info['volume_per_meter']
st.write(f"**Calculated Current Volume:** {current_volume:.2f} m³")

# Flow Inputs
st.subheader("Flow Inputs")
col1, col2 = st.columns(2)

with col1:
    no_inlet_flow = st.checkbox("No Inlet Flow")
    inlet_data = "" if no_inlet_flow else st.text_area("Paste Inlet Flow Data (Timestamp, m³/hr)", "2024-07-13 12:00,15\n2024-07-13 12:15,15\n2024-07-13 12:30,15")

with col2:
    no_outlet_flow = st.checkbox("No Outlet Flow")
    outlet_data = "" if no_outlet_flow else st.text_area("Paste Outlet Flow Data (Timestamp, m³/hr)", "2024-07-13 12:00,20\n2024-07-13 12:30,18")

# Button to Run Calculation
if st.button("Calculate Retention"):
    time_index = pd.date_range(start=pd.Timestamp.now().round('H'), periods=24, freq='H')
    df = pd.DataFrame(index=time_index)

    if no_inlet_flow:
        df['Inlet Flow'] = 0
    else:
        inlet_df = pd.DataFrame([x.split(',') for x in inlet_data.strip().split('\n')], columns=['Time', 'Flow'])
        inlet_df['Time'] = pd.to_datetime(inlet_df['Time'])
        inlet_df['Flow'] = inlet_df['Flow'].astype(float)
        inlet_df = inlet_df.set_index('Time').resample('H').mean().interpolate()
        df['Inlet Flow'] = inlet_df['Flow']

    if no_outlet_flow:
        df['Outlet Flow'] = 0
    else:
        outlet_df = pd.DataFrame([x.split(',') for x in outlet_data.strip().split('\n')], columns=['Time', 'Flow'])
        outlet_df['Time'] = pd.to_datetime(outlet_df['Time'])
        outlet_df['Flow'] = outlet_df.set_index('Time').resample('H').mean().interpolate()
        df['Outlet Flow'] = outlet_df['Flow']

    df['Net Flow (m³/hr)'] = df['Inlet Flow'] - df['Outlet Flow']
    df['Volume (m³)'] = current_volume + df['Net Flow (m³/hr)'].cumsum()
    df['Level (m)'] = df['Volume (m³)'] / srv_info['volume_per_meter']

    st.subheader("Predicted Reservoir Levels")
    st.dataframe(df[['Inlet Flow', 'Outlet Flow', 'Level (m)']])

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df['Level (m)'], marker='o', label='Reservoir Level (m)')
    ax.axhline(srv_info['operating_capacity'] / srv_info['volume_per_meter'], color='red', linestyle='--', label='Max Capacity')
    ax.set_xlabel("Time")
    ax.set_ylabel("Reservoir Level (m)")
    ax.set_title("Reservoir Level Over Time")
    ax.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig)

    st.success("Calculation complete! PDF export feature coming soon.")
