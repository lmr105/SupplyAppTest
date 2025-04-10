import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os

# --- Unit conversion factors for flows (to m³/s) ---
flow_conversion = {
    "L/s": 0.001,
    "m³/s": 1,
    "ML/d": 1e6 / 86400
}

# --- Rule-based calculation functions ---

def calculate_net_flow_retention(capacity, inlet_flow_m3s, outlet_flow_m3s):
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
    if rate_of_change_percent == 0:
        return None
    # Assume full tank if current level is not provided.
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
    if current_level_percent <= 0:
        return None
    return (surface_area * current_level_m * 100) / current_level_percent

def infer_capacity_from_net_flow(rate_of_change_percent, inlet_flow_m3s, outlet_flow_m3s):
    net_flow = outlet_flow_m3s - inlet_flow_m3s
    if rate_of_change_percent == 0 or net_flow <= 0:
        return None
    return (net_flow * 100) / abs(rate_of_change_percent)

def calculate_all_methods(params):
    results = []
    inlet_flow_m3s = (params.get("inlet_flow_value") * flow_conversion[params.get("inlet_flow_unit")]
                      if params.get("inlet_flow_value") else None)
    outlet_flow_m3s = (params.get("outlet_flow_value") * flow_conversion[params.get("outlet_flow_unit")]
                       if params.get("outlet_flow_value") else None)
    
    capacity = params.get("capacity")
    if capacity is None and params.get("current_level_m") and params.get("surface_area") and params.get("current_level_percent"):
        inferred_cap = infer_capacity(params["current_level_m"], params["surface_area"], params["current_level_percent"])
        if inferred_cap:
            results.append({
                "Method": "Inferred Capacity", 
                "Inference": f"Capacity inferred as {inferred_cap:.2f} m³ using current level, surface area, and % full."
            })
            capacity = inferred_cap

    if inlet_flow_m3s is not None and outlet_flow_m3s is not None and capacity:
        result = calculate_net_flow_retention(capacity, inlet_flow_m3s, outlet_flow_m3s)
        if result:
            results.append(result)
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
                
    if capacity:
        if inlet_flow_m3s is not None and outlet_flow_m3s is None:
            result = calculate_flow_based_retention_single(capacity, inlet_flow_m3s, "Inlet Flow")
            if result:
                results.append(result)
        if outlet_flow_m3s is not None and inlet_flow_m3s is None:
            result = calculate_flow_based_retention_single(capacity, outlet_flow_m3s, "Outlet Flow")
            if result:
                results.append(result)
    
    if params.get("rate_of_change_percent") is not None:
        current_pct = params.get("current_level_percent") if params.get("current_level_percent") is not None else 100
        result = calculate_rate_based_retention(current_pct, params["rate_of_change_percent"])
        if result:
            results.append(result)
    
    if params.get("current_level_m") is not None and params.get("rate_of_change_mph") is not None:
        result = calculate_geometric_retention_simple(params["current_level_m"], params["rate_of_change_mph"])
        if result:
            results.append(result)
    
    return results

# --- Load the Random Forest Model ---
@st.cache_resource
def load_rf_model():
    model_path = "models/train_rf_model.pkl"  # Updated file path (remove the '.py' extension)
    if os.path.exists(model_path):
        return joblib.load(model_path)
    else:
        return None

rf_model = load_rf_model()

st.title("Reservoir Retention Time Calculator")

st.markdown("""
Enter the reservoir data below. The app will attempt to:
- Use established physical relationships to compute retention times.
- Leverage a trained Random Forest model (if available) to predict retention time.
- Compare model predictions with rule-based calculations.
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
    
    # Rule-based calculations
    rule_based_results = calculate_all_methods(params)
    
    st.subheader(f"Retention Time Estimates for {reservoir_name}")
    results_list = []
    
    if rule_based_results and not all(r.get("Retention Time (hours)") is None for r in rule_based_results):
        results_list.extend(rule_based_results)
    
    # Random Forest Model Prediction
    feature_vector = [
        params.get("inlet_flow_value") or 0,
        params.get("outlet_flow_value") or 0,
        params.get("capacity") or 0,
        params.get("current_level_m") or 0,
        params.get("rate_of_change_percent") or 0,
        params.get("rate_of_change_mph") or 0,
        params.get("surface_area") or 0,
        params.get("current_level_percent") or 100
    ]
    
    if rf_model is not None:
        pred = rf_model.predict([feature_vector])[0]
        results_list.append({
            "Method": "Random Forest Prediction", 
            "Retention Time (hours)": pred, 
            "Accuracy (%)": "N/A",
            "Note": "Model prediction based on training data."
        })
    else:
        st.info("Random Forest model not found. Only rule-based calculations will be used.")
    
    if not results_list or all(r.get("Retention Time (hours)") is None for r in results_list):
        st.error("Insufficient or inconsistent data to calculate retention time. Please review your inputs.")
    else:
        df_results = pd.DataFrame(results_list)
        st.dataframe(df_results)
        
        if params.get("min_draw_down_level") and params.get("current_level_m"):
            if params["current_level_m"] < params["min_draw_down_level"]:
                st.warning("Warning: Current water level is below the Minimum Draw Down Level!")
        
        st.markdown("""
        **Note:** Rule-based calculations use established physical equations with inferred values where necessary.
        The Random Forest model (if available) provides a prediction based on historical or synthetic training data.
        """)
