# Streamlit app for tanker deployment decision support - Phase 1: Weighted Scoring Model
import streamlit as st

# Normalization ranges (min, max)
NORMALIZATION_RANGES = {
    'cml_impact': (0, 100000),           # £
    'maintenance_delay': (0, 300),       # minutes
    'tanker_resource': (0, 1),           # fraction (0 or 1)
    'assets_at_risk': (0, 1),            # yes/no (1/0)
    'critical_customers': (0, 1),        # yes/no (1/0)
    'cost_benefit_ratio': (0, 100000)    # £ saved per £ spent
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
    Compute composite score based on inputs dict of raw values.
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
    st.write("Phase 1: Weighted Scoring Model")

    # Sidebar inputs
    st.sidebar.header("Input Parameters")
    cml = st.sidebar.number_input(
        "CML Impact (cost £)", min_value=0.0, max_value=100000.0, value=0.0, step=100.0
    )
    delay = st.sidebar.number_input(
        "Maintenance delay (minutes)", min_value=0.0, max_value=300.0, value=0.0, step=5.0
    )
    tanker_ok = st.sidebar.radio(
        "Required tankers available and fit?", ("Yes", "No"), index=1
    )
    assets_risk = st.sidebar.radio(
        "Above-ground assets at risk?", ("Yes", "No"), index=1
    )
    critical_cust = st.sidebar.radio(
        "Critical customers affected?", ("Yes", "No"), index=1
    )
    cost_benefit = st.sidebar.number_input(
        "Cost-benefit ratio (£ saved per £ spent)", min_value=0.0, max_value=100000.0, value=0.0, step=100.0
    )

    # Map inputs to internal keys
    inputs = {
        'cml_impact': cml,
        'maintenance_delay': delay,
        'tanker_resource': 1 if tanker_ok == "Yes" else 0,
        'assets_at_risk': 1 if assets_risk == "Yes" else 0,
        'critical_customers': 1 if critical_cust == "Yes" else 0,
        'cost_benefit_ratio': cost_benefit
    }

    # Compute score and normalized breakdown
    score, breakdown = compute_score(inputs)

    st.subheader("Composite Score")
    st.metric("Score (0-1)", f"{score:.2f}")
    st.progress(score)

    # Recommendation
    if score >= THRESHOLD:
        st.success(f"Score ≥ {THRESHOLD}: Recommend to DEPLOY tankers.")
    else:
        st.error(f"Score < {THRESHOLD}: Recommend to HOLD OFF deploying tankers.")

    # Detailed breakdown
    st.subheader("Factor Breakdown (normalized)")
    for k, v in breakdown.items():
        st.write(f"**{k.replace('_', ' ').title()}:** {v:.2f} (weight {WEIGHTS[k]})")

    # TODO: Phase 2 - integrate ML model once historical data is available

if __name__ == "__main__":
    main()
