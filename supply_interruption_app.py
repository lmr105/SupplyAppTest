import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime, timedelta
from xlsxwriter.utility import xl_col_to_name

# Title
st.title("Supply Interruption Analysis Tool")

# BST Toggle
use_bst = st.checkbox("Apply BST Adjustment (Add 1 Hour to Output Times)")

# Upload section
pressure_file = st.file_uploader("Upload Pressure Data (.xlsx)", type=["xlsx"])
height_file = st.file_uploader("Upload Property Heights (.xlsx)", type=["xlsx"])

if pressure_file and height_file:
    # Read pressure data
    pressure_df = pd.read_excel(pressure_file)
    height_df = pd.read_excel(height_file)

    # Check and clean pressure data
    pressure_df.columns = pressure_df.columns.str.strip()
    pressure_df['Datetime'] = pd.to_datetime(pressure_df['Datetime'], dayfirst=True)
    pressure_df = pressure_df.sort_values('Datetime')

    # User inputs
    logger_height = st.number_input("Enter Logger Height (m)", value=100.0)
    additional_headloss = st.number_input("Enter Additional Headloss Allowance (m)", value=10.0)

    # Run Analysis button
    if st.button("Run Analysis"):
        all_results = []

        # For each property height
        for height in height_df['Property_Height'].unique():
            threshold = height - logger_height + additional_headloss
            in_supply = pressure_df['Pressure'] > threshold
            outages = []
            restored = []

            prev = in_supply.iloc[0]
            for idx in range(1, len(in_supply)):
                if prev and not in_supply.iloc[idx]:
                    outages.append(pressure_df['Datetime'].iloc[idx])
                if not prev and in_supply.iloc[idx]:
                    restored.append(pressure_df['Datetime'].iloc[idx])
                prev = in_supply.iloc[idx]

            # Adjust for BST if toggle is selected
            if use_bst:
                outages = [dt + timedelta(hours=1) for dt in outages]
                restored = [dt + timedelta(hours=1) for dt in restored]

            for i in range(len(outages)):
                try:
                    lost_time = outages[i]
                    regain_time = restored[i]
                    duration = regain_time - lost_time
                except IndexError:
                    lost_time = outages[i]
                    regain_time = None
                    duration = datetime.now() - lost_time

                outage_hours = duration.total_seconds() / 3600
                num_properties = height_df[height_df['Property_Height'] == height]['Total_Properties'].values[0]
                cml_impact = ((outage_hours * 24 * num_properties) / 1473786) * 60
                cost = cml_impact * 61000

                all_results.append({
                    "Property Height": height,
                    "Lost Supply": lost_time,
                    "Regained Supply": regain_time if regain_time else "Still Off",
                    "Outage Duration": str(duration).split('.')[0],
                    "CML Impact": round(cml_impact, 6),
                    "Cost": round(cost, 2)
                })

        result_df = pd.DataFrame(all_results)
        st.dataframe(result_df)

        # Total metrics
        total_cml = result_df['CML Impact'].sum()
        total_cost = result_df['Cost'].sum()
        st.markdown(f"**Total CML Impact:** {total_cml:.6f}")
        st.markdown(f"**Total Cost (GBP):** £{total_cost:,.2f}")

        # Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            result_df.to_excel(writer, sheet_name='Processed Results', index=False)
            writer.save()
        st.download_button(
            label="Download Processed Data as Excel (.xlsx)",
            data=output.getvalue(),
            file_name="processed_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
