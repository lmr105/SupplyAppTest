import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------
# Unit conversion factors (all flows to m³/s)
flow_conversion = {
    "L/s": 0.001,         # 1 L/s = 0.001 m³/s
    "m³/s": 1,
    "ML/d": 1e6 / 86400     # 1 Megalitre per day in m³/s
}

# ---------------------------
# FUNCTIONS FOR CALCULATIONS

def calculate_net_flow_retention(capacity, inlet_flow_m3s, outlet_flow_m3s):
    """
    Calculates retention time based on net flow:
      net_flow = outlet_flow_m3s - inlet_flow_m3s.
    If net_flow is positive (water leaving), then:
      T_ret = capacity / net_flow.
    Returns a dictionary with retention time in hours or a note if the tank is filling.
    """
    net_flow = outlet_flow_m3s - inlet_flow_m3s
    if net_flow <= 0:
        return {
            "Method": "Net Flow Retention", 
            "Retention Time (hours)": None, 
            "Accuracy (%)": 95,
            "Note": "The reservoir is filling or in balance."
        }
    retention_time_seconds = capacity / net_flow
    retention_time_hours = retention_time_seconds / 3600
    return {
        "Method": "Net Flow Retention", 
        "Retention Time (hours)": retention_time_hours, 
        "Accuracy (%)": 95,
        "Note": "Calculated using net flow (outlet - inlet)."
    }

def calculate_flow_based_retention_single(capacity, flow_m3s, flow_source="Flow"):
    """
    Calculates retention time if only one flow (inlet or outlet) is provided.
    The method assumes the provided flow approximates the effective outflow.
    """
    if flow_m3s <= 0 or capacity is None:
        return None
    retention_time_seconds = capacity / flow_m3s
    retention_time_hours = retention_time_seconds / 3600
    return {
        "Method": f"{flow_source} Flow Retention", 
        "Retention Time (hours)": retention_time_hours, 
        "Accuracy (%)": 85,
        "Note": f"Assuming {flow_source.lower()} flow represents outflow."
    }

def calculate_rate_based_retention(current_level_percent, rate_of_change_percent):
    """
    Estimates retention time using percentage-based data.
    If current_level_percent is not provided, assume a full tank (100%).
    Calculation: T_ret = (Current Level %) / |Rate-of-Change (%/hr)|.
    """
    if rate_of_change_percent == 0:
        return None
    # Assume full tank if current level not provided.
    current_level = current_level_percent if current_level_percent is not None else 100
    retention_time_hours = current_level / abs(rate_of_change_percent)
    note = "Using provided current level (%)." if current_level_percent is not None else "Assuming 100% fill (full tank)."
    return {
        "Method": "Rate-of-change (Percent)", 
        "Retention Time (hours)": retention_time_hours, 
        "Accuracy (%)": 70,
        "Note": note
    }

def calculate_geometric_retention_simple(current_level_m, rate_of_change_mph):
    """
    Estimates retention time based on level drop.
    T_ret = Current Level (m) / |Rate-of-Change (m/hr)|.
    This method requires only current level (in m) and rate of change in m/hr.
    """
    if rate_of_change_mph == 0:
        return None
    retention_time_hours = current_level_m / abs(rate_of_change_mph)
    return {
        "Method": "Geometric (Level Drop)", 
        "Retention Time (hours)": retention_time_hours, 
        "Accuracy (%)": 75,
        "Note": "Based on current water level and rate-of-change in m/hr."
    }

def infer_capacity(current_level_m, surface_area, current_level_percent):
    """
    Infers the total volumetric capacity if not directly provided.
    Uses:
       current_volume = surface_area * current_level_m,
       current_volume = capacity * (current_level_percent / 100).
    Rearranged:
       capacity = (surface_area * current_level_m * 100) / current_level_percent.
    """
    if current_level_percent <= 0:
        return None
    return (surface_area * current_level_m * 100) / current_level_percent

def infer_capacity_from_net_flow(rate_of_change_percent, inlet_flow_m3s, outlet_flow_m3s):
    """
    Alternative capacity inference using net flow and rate-of-change (%).
    Based on:
       rate_of_change (%) ≈ (net_flow / capacity) * 100  =>  capacity = (net_flow * 100) / |rate_of_change|
    """
    net_flow = outlet_flow_m3s - inlet_flow_m3s
    if rate_of_change_percent == 0 or net_flow <= 0:
        return None
    return (net_flow * 100) / abs(rate_of_change_percent)

def calculate_all_methods(params):
    """
    Determines which calculation methods can be applied based on available inputs.
    It will:
      - Infer missing capacity when possible.
      - Compute retention times using net flow, single flow, rate-of-change (%),
        and geometric (level drop) methods.
    Returns a list of dictionaries with the results.
    """
    results = []
    # Convert flow units to m³/s if provided.
    inlet_flow_m3s = (params.get("inlet_flow_value") * flow_conversion[params.get("inlet_flow_unit")]
                      if params.get("inlet_flow_value") else None)
    outlet_flow_m3s = (params.get("outlet_flow_value") * flow_conversion[params.get("outlet_flow_unit")]
                       if params.get("outlet_flow_value") else None)
    
    capacity = params.get("capacity")
    
    # --- Capacity Inference ---
    # If capacity is missing but we have enough geometric data, try inferring it.
    if capacity is None and params.get("current_level_m") and params.get("surface_area") and params.get("current_level_percent"):
        inferred_cap = infer_capacity(params["current_level_m"], params["surface_area"], params["current_level_percent"])
        if inferred_cap:
            results.append({
                "Method": "Inferred Capacity", 
                "Inference": f"Capacity inferred as {inferred_cap:.2f} m³ using current level (m), surface area (m²) and % full."
            })
            capacity = inferred_cap

    # --- Method 1: Net Flow Retention ---
    if inlet_flow_m3s is not None and outlet_flow_m3s is not None and capacity:
        result = calculate_net_flow_retention(capacity, inlet_flow_m3s, outlet_flow_m3s)
        if result:
            results.append(result)
    # If capacity is missing, but both flows and rate-of-change (%) exist, attempt an alternative capacity inference.
    elif capacity is None and inlet_flow_m3s is not None and outlet_flow_m3s is not None and params.get("rate_of_change_percent"):
        inferred_cap = infer_capacity_from_net_flow(params["rate_of_change_percent"], inlet_flow_m3s, outlet_flow_m3s)
        if inferred_cap:
            results.append({
                "Method": "Inferred Capacity from Net Flow", 
                "Inference": f"Capacity inferred as {inferred_cap:.2f} m³ using net flow and rate-of-change."
            })
            capacity = inferred_cap
            result = calculate_net_flow_retention(capacity, inlet_flow_m3s, outlet_flow_m3s)
            if result:
                results.append(result)
                
    # --- Method 2: Single Flow Retention ---
    if capacity:
        if inlet_flow_m3s is not None and outlet_flow_m3s is None:
            result = calculate_flow_based_retention_single(capacity, inlet_flow_m3s, "Inlet Flow")
            if result:
                results.append(result)
        if outlet_flow_m3s is not None and inlet_flow_m3s is None:
            result = calculate_flow_based_retention_single(capacity, outlet_flow_m3s, "Outlet Flow")
            if result:
                results.append(result)
    
    # --- Method 3: Rate-of-change Based (Percentage) ---
    # If current_level_percent is missing, assume full tank (100%) for this method.
    if params.get("rate_of_change_percent") is not None:
        current_pct = params.get("current_level_percent") if params.get("current_level_percent") is not None else 100
        result = calculate_rate_based_retention(current_pct, params["rate_of_change_percent"])
        if result:
            results.append(result)
    
    # --- Method 4: Geometric (Level Drop) ---
    # This method needs only current level in m and rate-of-change in m/hr.
    if params.get("current_level_m") is not None and params.get("rate_of_change_mph") is not None:
        result = calculate_geometric_retention_simple(params["current_level_m"], params["rate_of_change_mph"])
        if result:
            results.append(result)
    
    return results

# ---------------------------
# Streamlit App UI

st.title("Reservoir Retention Time Calculator")

st.markdown("""
Enter the reservoir data below. The app will:
- Infer missing values (for example, capacity) when possible.
- Calculate retention time using multiple methods and input combinations.
- Use assumptions (e.g. assume full tank if current level % is missing) where appropriate.
- Provide an accuracy score and notes for each method.
""")

with st.form(key="reservoir_form"):
    reservoir_name = st.text_input("Reservoir Name")
    
    st.subheader("Flow Data")
    inlet_flow_value = st.number_input("Inlet Flow Value", min_value=0.0, value=0.0, 
                                        help="Enter inlet flow value (if available)")
    inlet_flow_unit = st.selectbox("Inlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    
    outlet_flow_value = st.number_input("Outlet Flow Value", min_value=0.0, value=0.0, 
                                         help="Enter outlet flow value (if available)")
    outlet_flow_unit = st.selectbox("Outlet Flow Unit", options=list(flow_conversion.keys()), index=0)
    
    st.subheader("Reservoir Volume and Level")
    capacity = st.number_input("Total Volumetric Capacity (m³)", min_value=0.0, value=0.0, 
                               help="Enter total capacity if known; leave 0 if unknown.")
    current_level_percent = st.number_input("Current Level (%)", min_value=0.0, max_value=100.0, value=0.0, 
                                            help="Current water level as a percentage (if available).")
    current_level_m = st.number_input("Current Level (m)", min_value=0.0, value=0.0, 
                                      help="Current water level in meters (if available).")
    
    st.subheader("Rate of Change")
    rate_of_change_percent = st.number_input("Rate of Change (%/hr)", value=0.0, 
                                             help="Rate of change in percent per hour (e.g., -5 for a 5% drop per hour)")
    rate_of_change_mph = st.number_input("Rate of Change (m/hr)", value=0.0, 
                                         help="Rate of change in water level in meters per hour (e.g., -0.2)")
    
    st.subheader("Geometric Data (if available)")
    surface_area = st.number_input("Surface Area (m²)", min_value=0.0, value=0.0, 
                                   help="Surface area of the reservoir in square meters")
    
    st.subheader("Additional Parameters")
    min_draw_down_level = st.number_input("Minimum Draw Down Level (m)", min_value=0.0, value=0.0, 
                                          help="Minimum draw down level if known (optional)")
    
    submitted = st.form_submit_button("Calculate Retention Time")

if submitted:
    # Build parameters dictionary (0 values converted to None for optional data)
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
    
    # Compute all possible retention time estimates
    results = calculate_all_methods(params)
    
    # Check if any method produced a retention time
    if not results or all(r.get("Retention Time (hours)") is None for r in results):
        st.error("Insufficient or inconsistent data to calculate retention time. Please review your inputs.")
    else:
        st.subheader(f"Retention Time Estimates for {reservoir_name}")
        df = pd.DataFrame(results)
        st.dataframe(df)
        
        # Display a warning if the current water level is below the minimum draw down level.
        if params.get("min_draw_down_level") and params.get("current_level_m"):
            if params["current_level_m"] < params["min_draw_down_level"]:
                st.warning("Warning: Current water level is below the Minimum Draw Down Level!")
        
        st.markdown("""
        **Note:** Calculations are based on provided data. Inferred values and assumptions are used where data is missing.
        Accuracy percentages indicate relative confidence in each method.
        """)

