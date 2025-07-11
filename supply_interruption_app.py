# Streamlit app for tanker deployment decision support - Phase 1: Weighted Scoring & Detailed Calculations
import streamlit as st
import datetime
import math

# Constants for tanker types
TANKER_INFO = {
    'Artic': {'capacity': 25, 'cost_per_fill': 1000},
    'Rigid': {'capacity': 18, 'cost_per_fill': 600},
    'Hookloader': {'capacity': 13, 'cost_per_fill': 400}
}

# Normalization ranges (min, max)
NORMALIZATION_RANGES = {
    'cml_impact': (0, 100000),           # £
    'maintenance_delay': (0, 300),       # minutes
    'tanker_resource': (0, 1),           # fraction
    'assets_at_risk': (0, 1),            # binary
    'critical_customers': (0, 1),        # binary
    'cost_benefit_ratio': (0, 100)       # ratio
}

# Weights for each factor (sum = 1)
WEIGHTS = {
    'cml_impact': 0.1,
    'maintenance_delay': 0.1,
    'tanker_resource': 0.3,
    'assets_at_risk': 0.1,
    'critical_customers': 0.1,
    'cost_benefit_ratio': 0.3
}

# Decision threshold
THRESHOLD = 0.7


def normalize(value, bounds):
    """
    Normalize value to 0-1 based on bounds = (min, max).
    Caps to [0,1].
    """
    min_val, max_val = bounds
    if max_val == min_val:
        return 0.0
    f = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, f))


def compute_score(inputs):
    """
    Compute composite score based on normalized inputs.
    """
    scores = {}
    for key, raw in inputs.items():
        bounds = NORMALIZATION_RANGES[key]
        if key == 'maintenance_delay':
            # Lower delay is better: invert normalization
            norm = 1 - normalize(raw, bounds)
        else:
            norm = normalize(raw, bounds)
        scores[key] = norm
    # Composite score
    S = sum(WEIGHTS[k] * scores[k] for k in scores)
    return S, scores


def main():
    st.title("Tanker Deployment Decision Support")
    st.write("Phase 1: Weighted Scoring Model with Detailed Calculations")

    # --- CML Impact Calculation ---
    st.sidebar.header("CML Impact Inputs")
    num_props = st.sidebar.number_input("Properties affected", 0, 100000, 0)
    duration = st.sidebar.time_input("Duration out of supply (HH:MM)", datetime.time(0,0))
    # Convert to hours
    duration_hours = duration.hour + duration.minute / 60.0
    # Formula: (((props * hours * 60 * 24)/(60/1473786))*60)*610000
    cml_cost = (((num_props * duration_hours * 60 * 24) / (60/1473786)) * 60) * 610000
    st.sidebar.markdown(f"**CML Impact Cost:** £{cml_cost:,.2f}")

    # --- Maintenance Delay ---
    st.sidebar.header("Maintenance Delay Inputs")
    delay_h = st.sidebar.number_input("Repair delay hours", 0, 23, 0)
    delay_m = st.sidebar.number_input("Repair delay minutes", 0, 59, 0)
    delay_mins = delay_h*60 + delay_m

    # --- Flow & Tanker Calculation ---
    st.sidebar.header("Flow & Tanker Inputs")
    night_flow = st.sidebar.number_input("Nightline Flow (m³/hr)", 0.0, 10000.0, 0.0)
    peak_flow = st.sidebar.number_input("Peak Flow (m³/hr)", 0.0, 20000.0, 0.0)
    mean_flow = (night_flow + peak_flow) / 2
    st.sidebar.markdown(f"**Mean Average Flow:** {mean_flow:.1f} m³/hr")

    # Tanker selection & availability
    types = st.sidebar.multiselect("Available Tanker Types", list(TANKER_INFO.keys()), default=[])
    available = {}
    for t in types:
        available[t] = st.sidebar.number_input(f"# Available {t} tankers", 0, 100, 0)

    # Fill time
    fill_h = st.sidebar.number_input("Fill time hours", 0, 23, 0)
    fill_m = st.sidebar.number_input("Fill time minutes", 0, 120, 0)
    fill_hours = fill_h + fill_m/60.0

    # Calculate delivered flow rate and tanker resource ratio
    delivered_rate = 0.0
    cost_deployment = 0.0
    if fill_hours > 0 and mean_flow > 0:
        for t, count in available.items():
            cap = TANKER_INFO[t]['capacity']
            delivered_rate += (count * cap) / fill_hours
            cost_deployment += count * TANKER_INFO[t]['cost_per_fill']
    tanker_resource_ratio = min(delivered_rate / mean_flow, 1.0) if mean_flow>0 else 1.0
    st.sidebar.markdown(f"**Delivered Rate:** {delivered_rate:.1f} m³/hr")
    st.sidebar.markdown(f"**Deployment Cost (per cycle):** £{cost_deployment:,.2f}")
    st.sidebar.markdown(f"**Tanker Resource Ratio:** {tanker_resource_ratio:.2f}")
    if fill_hours*60 > 30:
        st.sidebar.warning("Fill time > 30 minutes may breach supply between cycles.")

    # --- Other Risks ---
    st.sidebar.header("Other Risk Inputs")
    assets_risk = st.sidebar.radio("Assets at risk?", ("Yes","No"))
    critical_cust = st.sidebar.radio("Critical customers affected?", ("Yes","No"))

    # --- Prepare inputs for scoring ---
    inputs = {
        'cml_impact': cml_cost,
        'maintenance_delay': delay_mins,
        'tanker_resource': tanker_resource_ratio,
        'assets_at_risk': 1 if assets_risk=="Yes" else 0,
        'critical_customers': 1 if critical_cust=="Yes" else 0,
        'cost_benefit_ratio': (cml_cost / cost_deployment) if cost_deployment>0 else 0
    }

    # --- Compute Score ---
    score, breakdown = compute_score(inputs)

    # --- Display Results ---
    st.subheader("Composite Score & Recommendation")
    st.metric("Score (0–1)", f"{score:.2f}")
    st.progress(score)
    if score >= THRESHOLD:
        st.success(f"Score ≥ {THRESHOLD}: Deploy tankers.")
    else:
        st.error(f"Score < {THRESHOLD}: Hold off deploying tankers.")

    st.subheader("Normalized Factor Breakdown")
    for k,v in breakdown.items():
        st.write(f"**{k.replace('_',' ').title()}:** {v:.2f} (weight {WEIGHTS[k]})")

    st.subheader("Summary of Key Calculations")
    st.write(f"- CML Cost: £{cml_cost:,.2f}")
    st.write(f"- Mean Flow: {mean_flow:.1f} m³/hr")
    st.write(f"- Delivered Rate: {delivered_rate:.1f} m³/hr")
    st.write(f"- Tanker Resource Ratio: {tanker_resource_ratio:.2f}")
    st.write(f"- Deployment Cost per Cycle: £{cost_deployment:,.2f}")
    st.write(f"- Cost-Benefit Ratio: {inputs['cost_benefit_ratio']:.2f}")

if __name__ == "__main__":
    main()
