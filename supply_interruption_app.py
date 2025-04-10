import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ---------------------------
# Unit conversion factors
flow_conversion = {
    "L/s": 0.001,      # 1 L/s = 0.001 m³/s
    "m³/s": 1,
    "ML/d": 1e6 / 86400  # 1 Megalitre per day in m³/s
}

# ---------------------------
# FUNCTIONS FOR CALCULATIONS

def generate_schedule_netflow(params):
    """
    Primary method using inlet and outlet flows.
    Assumes:
      - Total capacity is known (m³)
      - Flows are provided (and converted to m³/s)
      - Current fill is known (as a percentage, default 100%)
      - Optionally, if surface_area (m²) is provided, water depth can be computed.
    Returns a DataFrame with hourly predictions until the reservoir is empty.
    """
    # Extract and convert inputs
    inlet_flow = params.get("inlet_flow_value")
    outlet_flow = params.get("outlet_flow_value")
    capacity = params.get("capacity")
    fill_pct = params.get("current_fill_pct")  # user-provided current fill percentage, default 100%
    if fill_pct is None:
        fill_pct = 100  # assume full tank if not provided
    inlet_flow_m3s = inlet_flow * flow_conversion[params.get("inlet_flow_unit")]
    outlet_flow_m3s = outlet_flow * flow_conversion[params.get("outlet_flow_unit")]
    
    # Net flow (m³/s); for emptying the tank, outlet must be greater than inlet
    net_flow = outlet_flow_m3s - inlet_flow_m3s
    if net_flow <= 0:
        st.error("Using flows, the net flow is not positive (outlet must exceed inlet for emptying).")
        return None

    # Current water volume (m³)
    current_volume = capacity * (fill_pct / 100)
    # Water drained per hour (m³)
    drained_per_hour = net_flow * 3600

    # Calculate time to empty (in hours)
    hours_to_empty = current_volume / drained_per_hour
    num_hours = int(np.ceil(hours_to_empty))
    
    # Generate schedule data
    schedule = []
    start_time = datetime.now()
    for i in range(num_hours + 1):
        time_step = start_time + timedelta(hours=i)
        vol = max(current_volume - drained_per_hour * i, 0)
        fill = (vol / capacity) * 100 if capacity > 0 else 0
        # If surface_area provided, compute water depth:
        water_depth = None
        if params.get("surface_area"):
            water_depth = vol / params.get("surface_area")
        # Prepare a comments field if a minimum drawdown level is provided
        comment = ""
        if params.get("min_draw_down_level") and water_depth is not None:
            if water_depth < params.get("min_draw_down_level"):
                comment = "Below Minimum Draw Down"
        schedule.append({
            "Time": time_step.strftime("%Y-%m-%d %H:%M"),
            "Predicted Volume (m³)": round(vol, 2),
            "Predicted Fill (%)": round(fill, 1),
            "Predicted Depth (m)": round(water_depth, 2) if water_depth is not None else "N/A",
            "Comments": comment
        })
    return pd.DataFrame(schedule)

def generate_schedule_rate_pct(params):
    """
    Fallback method using rate-of-change in percentage per hour.
    Assumes:
      - Current fill percentage (default 100% if not provided).
      - Rate-of-change (in %/hr), expected to be negative.
      - Total capacity may be used to compute volume if provided; otherwise, only fill % is predicted.
    Returns a DataFrame with hourly predictions of fill percentage.
    """
    rate_pct = params.get("rate_of_change_pct")
    if rate_pct is None or rate_pct == 0:
        st.error("Rate-of-change (%/hr) is required for this method.")
        return None
    current_fill = params.get("current_fill_pct")
    if current_fill is None:
        current_fill = 100
    capacity = params.get("capacity")
    num_hours = int(np.ceil(current_fill / abs(rate_pct)))
    
    schedule = []
    start_time = datetime.now()
    for i in range(num_hours + 1):
        time_step = start_time + timedelta(hours=i)
        fill = max(current_fill - abs(rate_pct) * i, 0)
        vol = capacity * (fill / 100) if capacity else None
        water_depth = None
        if capacity and params.get("surface_area"):
            water_depth = vol / params.get("surface_area")
        comment = ""
        if params.get("min_draw_down_level") and water_depth is not None:
            if water_depth < params.get("min_draw_down_level"):
                comment = "Below Minimum Draw Down"
        schedule.append({
            "Time": time_step.strftime("%Y-%m-%d %H:%M"),
            "Predicted Fill (%)": round(fill, 1),
            "Predicted Volume (m³)": round(vol, 2) if vol is not None else "N/A",
            "Predicted Depth (m)": round(water_depth, 2) if water_depth is not None else "N/A",
            "Comments": comment
        })
    return pd.DataFrame(schedule)

def generate_schedule_rate_m(params):
    """
    Fallback method using rate-of-change in water level (m/hr).
    Assumes:
      - Current water level in meters is provided.
      - Rate-of-change (in m/hr) is provided (expected negative for emptying).
    Returns a DataFrame with hourly predictions of water depth.
    """
    rate_m = params.get("rate_of_change_m")
    current_depth = params.get("current_level_m")
    if rate_m is None or rate_m == 0 or current_depth is None:
        st.error("Current water level and rate-of-change in m/hr are required for this method.")
        return None
    num_hours = int(np.ceil(current_depth / abs(rate_m)))
    
    schedule = []
    start_time = datetime.now()
    for i in range(num_hours + 1):
        time_step = start_time + timedelta(hours=i)
        depth = max(current_depth + rate_m * i, 0)  # rate_m is negative for emptying
        comment = ""
        if params.get("min_draw_down_level"):
            if depth < params.get("min_draw_down_level"):
                comment = "Below Minimum Draw Down"
        schedule.append({
            "Time": time_step.strftime("%Y-%m-%d %H:%M"),
            "Predicted Depth (m)": round(depth, 2),
            "Comments": comment
        })
    return pd.DataFrame(schedule)

# ---------------------------
# Streamlit App UI

st.title("Reservoir Emptying Calculator")

st.markdown("""
This application predicts how long it will take for a reservoir to empty in an emergency,
and generates an hourly schedule of the predicted water level. The primary method uses flow data
(if available), and fallback methods based on rate-of-change measurements are provided.
""")

with st.form(key="input_form"):
    st.subheader("Flow Data (if available)")
    inlet_flow_value = st.number_input("Inlet Flow Value", min_value=0.0, value=0.0, help="Enter inlet flow (e.g., in L/s)")
    inlet_flow_unit = st.selectbox("Inlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    outlet_flow_value = st.number_input("Outlet Flow Value", min_value=0.0, value=0.0, help="Enter outlet flow (e.g., in L/s)")
    outlet_flow_unit = st.selectbox("Outlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    
    st.subheader("Tank & Geometry Data")
    capacity = st.number_input("Total Volumetric Capacity (m³)", min_value=0.0, value=0.0,
                                 help="Enter total capacity (if known)")
    current_fill_pct = st.number_input("Current Fill (%)", min_value=0.0, max_value=100.0, value=100.0,
                                         help="Enter the current fill percentage (default 100%)")
    # For depth prediction with flows, you need surface area
    surface_area = st.number_input("Surface Area (m²)", min_value=0.0, value=0.0,
                                   help="Enter surface area (if known) to compute water depth from volume")
    # Alternatively, if flows are not used, user can specify current water level (m)
    current_level_m = st.number_input("Current Water Level (m)", min_value=0.0, value=0.0,
                                      help="Enter current water level in meters (for rate-of-change in m/hr)")
    
    st.subheader("Dynamic Data (choose one fallback if flows are not available)")
    rate_of_change_pct = st.number_input("Rate of Change (%/hr)", value=0.0,
                                           help="Enter the rate-of-change in percent per hour (e.g., -5 for a 5% drop/hr)")
    rate_of_change_m = st.number_input("Rate of Change (m/hr)", value=0.0,
                                       help="Enter the rate-of-change in meters per hour (e.g., -0.2)")
    
    st.subheader("Additional Parameters")
    min_draw_down_level = st.number_input("Minimum Draw Down Level (m)", min_value=0.0, value=0.0,
                                          help="Enter minimum draw down level to flag warnings")
    
    submitted = st.form_submit_button("Calculate Emptying Schedule")

# Build a parameters dictionary for easier use
params = {
    "inlet_flow_value": inlet_flow_value if inlet_flow_value > 0 else None,
    "inlet_flow_unit": inlet_flow_unit,
    "outlet_flow_value": outlet_flow_value if outlet_flow_value > 0 else None,
    "outlet_flow_unit": outlet_flow_unit,
    "capacity": capacity if capacity > 0 else None,
    "current_fill_pct": current_fill_pct if current_fill_pct > 0 else None,
    "surface_area": surface_area if surface_area > 0 else None,
    "current_level_m": current_level_m if current_level_m > 0 else None,
    "rate_of_change_pct": rate_of_change_pct if rate_of_change_pct != 0 else None,
    "rate_of_change_m": rate_of_change_m if rate_of_change_m != 0 else None,
    "min_draw_down_level": min_draw_down_level if min_draw_down_level > 0 else None
}

if submitted:
    schedule_df = None
    method_used = ""
    # Primary: Use net flow method if flows and capacity are provided
    if (params.get("inlet_flow_value") and params.get("outlet_flow_value") and params.get("capacity")):
        schedule_df = generate_schedule_netflow(params)
        method_used = "Net Flow Method (using flows and capacity)"
    # Fallback: If net flow method not available, check if rate-of-change percentage is provided
    elif params.get("rate_of_change_pct"):
        schedule_df = generate_schedule_rate_pct(params)
        method_used = "Rate-of-Change (%) Method"
    # Fallback: If rate-of-change in m/hr is provided
    elif params.get("rate_of_change_m") and params.get("current_level_m"):
        schedule_df = generate_schedule_rate_m(params)
        method_used = "Rate-of-Change (m/hr) Method"
    
    if schedule_df is None:
        st.error("Insufficient or inconsistent data to produce a schedule. Please verify your inputs.")
    else:
        st.subheader(f"Emptying Schedule using {method_used}")
        st.dataframe(schedule_df)
        st.markdown("""
        **Notes:**
        - The predictions are made in 1‑hour intervals from the current time.
        - Water levels, fill percentages, and volumes are estimated using a linear decline model.
        - Rows showing a predicted water depth below the minimum draw down level are flagged in the Comments.
        - The results are approximations (±10% accuracy is acceptable in emergency scenarios).
        """)

