import streamlit as st
import pandas as pd
import numpy as np

# ------------------------------------------------
# Unit conversion factors to standard units:
# For flows: convert all to cubic meters per second (m³/s)
flow_conversion = {
    "L/s": 0.001,           # 1 L/s = 0.001 m³/s
    "m³/s": 1,
    "ML/d": 1e6 / 86400      # 1 Megalitre per day
}

# ------------------------------------------------
# Functions for calculations
def calculate_flow_based_retention(capacity, flow_m3s, method_label):
    """
    Calculates retention time based on volumetric capacity (m³) and a flow rate (m³/s).
    Returns the retention time in hours.
    """
    if flow_m3s <= 0:
        return None  # Avoid division by zero or negative flows
    retention_time_seconds = capacity / flow_m3s
    retention_time_hours = retention_time_seconds / 3600
    return {"Method": method_label, "Retention Time (hours)": retention_time_hours, "Accuracy (%)": 95 if method_label=="Flow-based (Inlet & Outlet)" else 85}

def calculate_rate_based_retention(current_level_percent, rate_of_change_percent):
    """
    Calculate retention time using percentage-based data.
    Returns the retention time in hours.
    """
    if rate_of_change_percent == 0:
        return None
    retention_time_hours = current_level_percent / abs(rate_of_change_percent)
    return {"Method": "Rate-of-change-based (%/h)", "Retention Time (hours)": retention_time_hours, "Accuracy (%)": 70}

def calculate_geometric_retention(surface_area, current_level_m, rate_of_change_mph):
    """
    Calculate retention time based on a geometric approach:
      current water volume = surface_area * current_level (assumes uniform cross-section)
      dV/dt = surface_area * |rate of change in level|
    """
    if rate_of_change_mph == 0:
        return None
    current_volume = surface_area * current_level_m  # in m³
    dV_dt = surface_area * abs(rate_of_change_mph)      # m³ per hour
    retention_time_hours = current_volume / dV_dt
    return {"Method": "Geometric (Surface Area-based)", "Retention Time (hours)": retention_time_hours, "Accuracy (%)": 75}

def calculate_all_methods(params):
    """
    Given a dictionary of parameters, try to apply all available calculation methods.
    Return a list of method results.
    """
    results = []
    
    # Flow-based method if outlet flow is provided
    if params.get("inlet_flow_value") is not None and params.get("outlet_flow_value") is not None:
        # Convert flows to m³/s based on the selected units
        inlet_flow_m3s = params["inlet_flow_value"] * flow_conversion[params["inlet_flow_unit"]]
        outlet_flow_m3s = params["outlet_flow_value"] * flow_conversion[params["outlet_flow_unit"]]
        
        # If flows are both positive, we choose the outlet flow as the more representative (typical for withdrawal calculations)
        result = calculate_flow_based_retention(params["capacity"], outlet_flow_m3s, "Flow-based (Inlet & Outlet)")
        if result: results.append(result)
    
    # Alternate: if only one of the flows is provided
    elif params.get("inlet_flow_value") is not None:
        inlet_flow_m3s = params["inlet_flow_value"] * flow_conversion[params["inlet_flow_unit"]]
        result = calculate_flow_based_retention(params["capacity"], inlet_flow_m3s, "Flow-based (Inlet Flow Only)")
        if result: results.append(result)
    elif params.get("outlet_flow_value") is not None:
        outlet_flow_m3s = params["outlet_flow_value"] * flow_conversion[params["outlet_flow_unit"]]
        result = calculate_flow_based_retention(params["capacity"], outlet_flow_m3s, "Flow-based (Outlet Flow Only)")
        if result: results.append(result)
    
    # Rate-of-change based method (using %)
    if params.get("current_level_percent") is not None and params.get("rate_of_change_percent") is not None:
        result = calculate_rate_based_retention(params["current_level_percent"], params["rate_of_change_percent"])
        if result: results.append(result)
    
    # Geometric method (using surface area, current level in m, and rate of change in m/h)
    if (params.get("current_level_m") is not None and 
        params.get("surface_area") is not None and 
        params.get("rate_of_change_mph") is not None):
        result = calculate_geometric_retention(params["surface_area"], params["current_level_m"], params["rate_of_change_mph"])
        if result: results.append(result)
    
    return results

# ------------------------------------------------
# Streamlit App

st.title("Reservoir Retention Time Calculator")

st.markdown("Enter the reservoir data below. You can provide as many parameters as you have, and the app will use the best available data to calculate the retention time.")

with st.form(key="reservoir_form"):
    reservoir_name = st.text_input("Reservoir Name")
    
    st.subheader("Flow Data")
    inlet_flow_value = st.number_input("Inlet Flow Value", min_value=0.0, value=0.0, help="Enter inlet flow value (if available)")
    inlet_flow_unit = st.selectbox("Inlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    
    outlet_flow_value = st.number_input("Outlet Flow Value", min_value=0.0, value=0.0, help="Enter outlet flow value (if available)")
    outlet_flow_unit = st.selectbox("Outlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    
    st.subheader("Reservoir Volume and Level")
    capacity = st.number_input("Total Volumetric Capacity (m³)", min_value=0.0, value=0.0, help="Total reservoir capacity in m³")
    current_level_percent = st.number_input("Current Level (%)", min_value=0.0, max_value=100.0, value=0.0, help="Current water level as percentage")
    current_level_m = st.number_input("Current Level (m)", min_value=0.0, value=0.0, help="Current water level measured in meters")
    
    st.subheader("Rate of Change")
    rate_of_change_percent = st.number_input("Rate of Change (%/hr)", value=0.0, help="Rate of change in percent per hour (e.g., -5 for a 5% drop per hour)")
    rate_of_change_mph = st.number_input("Rate of Change (m/hr)", value=0.0, help="Rate of change in water depth per hour (m/hr)")
    
    st.subheader("Geometric Data (if available)")
    surface_area = st.number_input("Surface Area (m²)", min_value=0.0, value=0.0, help="Surface area of the reservoir")
    # Additional geometric inputs (e.g., full depth) could be added here if needed.
    
    # Minimum Draw Down Level (optional) for warning visualization later
    min_draw_down_level = st.number_input("Minimum Draw Down Level (m)", min_value=0.0, value=0.0, help="Input the minimum draw down level if known (optional)")
    
    submitted = st.form_submit_button("Calculate Retention Time")

if submitted:
    # Prepare parameter dictionary. We treat zero as "not provided" for flows and capacity fields if that makes sense.
    params = {
        "inlet_flow_value": inlet_flow_value if inlet_flow_value > 0 else None,
        "inlet_flow_unit": inlet_flow_unit,
        "outlet_flow_value": outlet_flow_value if outlet_flow_value > 0 else None,
        "outlet_flow_unit": outlet_flow_unit,
        "capacity": capacity if capacity > 0 else None,
        "current_level_percent": current_level_percent if current_level_percent > 0 else None,
        "current_level_m": current_level_m if current_level_m > 0 else None,
        "rate_of_change_percent": rate_of_change_percent if rate_of_change_percent != 0 else None,
        "rate_of_change_mph": rate_of_change_mph if rate_of_change_mph != 0 else None,
        "surface_area": surface_area if surface_area > 0 else None,
        "min_draw_down_level": min_draw_down_level if min_draw_down_level > 0 else None
    }
    
    # Basic data validation: at least one method should be calculable
    results = calculate_all_methods(params)
    if not results:
        st.error("Insufficient data to calculate retention time. Please provide at least one valid dataset (flow data, rate of change or geometric data).")
    else:
        df_results = pd.DataFrame(results)
        st.subheader(f"Retention Time Estimates for {reservoir_name}")
        st.dataframe(df_results)
        
        # Example trend chart: if you plan to run the calculation over time,
        # you might store historical values in a session_state list and then plot.
        # For now, we simply display the computed values.
        st.markdown("**Note:** The accuracy score is an estimate based on the available data. In emergency scenarios, even a 'ball park' figure can aid rapid decision-making.")

        # Optional: Add warning lines (e.g., if current_level_m is near minimum draw down level)
        if params.get("min_draw_down_level") is not None and params.get("current_level_m") is not None:
            if params["current_level_m"] < params["min_draw_down_level"]:
                st.warning("The current water level is below the Minimum Draw Down Level!")
                
        st.markdown("---")
        st.markdown("This basic app can be extended further. For example, you could log each calculation over time to create a trend analysis or include additional methods as more telemetry becomes available.")

