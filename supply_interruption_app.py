import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta

# ------------------- Helper functions -------------------

def get_supply_interruptions(supply_status, timestamps):
    interruptions = []
    in_outage = False
    lost_time = None
    for i in range(len(supply_status)):
        if not supply_status[i] and not in_outage:
            in_outage = True
            lost_time = timestamps[i]
        elif supply_status[i] and in_outage:
            in_outage = False
            regained_time = timestamps[i]
            duration = (regained_time - lost_time).total_seconds() / 60
            interruptions.append({
                'Lost Time': lost_time,
                'Regained Time': regained_time,
                'Duration (mins)': duration
            })
    if in_outage:
        regained_time = timestamps.iloc[-1]
        duration = (regained_time - lost_time).total_seconds() / 60
        interruptions.append({
            'Lost Time': lost_time,
            'Regained Time': regained_time,
            'Duration (mins)': duration
        })
    return interruptions

def process_interruptions(df, min_duration=180, merge_gap=60):
    processed = []
    current = None
    for _, row in df.iterrows():
        if current is None:
            current = row
        else:
            gap = (row['Lost Time'] - current['Regained Time']).total_seconds() / 60
            if gap <= merge_gap:
                current['Regained Time'] = row['Regained Time']
                current['Duration (mins)'] = (current['Regained Time'] - current['Lost Time']).total_seconds() / 60
            else:
                if current['Duration (mins)'] >= min_duration:
                    processed.append(current)
                current = row
    if current is not None and current['Duration (mins)'] >= min_duration:
        processed.append(current)
    return pd.DataFrame(processed)

# ------------------- Streamlit UI -------------------

st.title("CML Supply Interruption Tool")

st.markdown("### Paste Pressure Logger Data (Timestamp, Pressure)")
pressure_data_text = st.text_area("Paste CSV-formatted pressure data here", height=200)

st.markdown("### Paste Property Heights (Property, Height)")
property_data_text = st.text_area("Paste CSV-formatted property height data here", height=150)

logger_height = st.number_input("Logger Height (m)", value=0.0)
additional_headloss = st.number_input("Additional Headloss (m)", value=0.0)
apply_bst = st.checkbox("Apply BST adjustment")

if pressure_data_text and property_data_text:
    # Read pasted data into DataFrames
    from io import StringIO
    pressure_df = pd.read_csv(StringIO(pressure_data_text), parse_dates=[0])
    pressure_df.columns = ['Timestamp', 'Pressure']
    pressure_df['Timestamp'] = pd.to_datetime(pressure_df['Timestamp'])
    if apply_bst:
        pressure_df['Timestamp'] = pressure_df['Timestamp'] + pd.to_timedelta(1, unit='h')

    property_heights = pd.read_csv(StringIO(property_data_text))
    property_heights.columns = ['Property', 'Height']

    results = {}
    processed_results = {}

    for _, row in property_heights.iterrows():
        property_name = row['Property']
        property_height = row['Height']

        # --- NEW LOGIC STARTS HERE ---
        pressure_df['Modified_Pressure'] = pressure_df['Pressure'] - additional_headloss
        pressure_df['Effective_Supply_Head'] = logger_height + (pressure_df['Modified_Pressure'] - 3)
        pressure_df['In_Supply'] = pressure_df['Effective_Supply_Head'] >= property_height
        # --- NEW LOGIC ENDS HERE ---

        interruptions = get_supply_interruptions(pressure_df['In_Supply'].values, pressure_df['Timestamp'])
        results[property_name] = interruptions

        if interruptions:
            int_df = pd.DataFrame(interruptions)
            proc_df = process_interruptions(int_df)
            if not proc_df.empty:
                proc_df['Property'] = property_name
                processed_results[property_name] = proc_df

    # Export results
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for property_name, interruptions in results.items():
            if interruptions:
                pd.DataFrame(interruptions).to_excel(writer, sheet_name=f"{property_name}_Raw", index=False)
        for property_name, proc_df in processed_results.items():
            proc_df.to_excel(writer, sheet_name=f"{property_name}_Processed", index=False)
    output.seek(0)

    st.download_button(
        label="Download Results Excel",
        data=output,
        file_name="Supply_Interruptions.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
