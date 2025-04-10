import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

# --- Generate Synthetic Data ---
# For demonstration: suppose we have 1000 samples.
# In practice, you would use real or more sophisticated simulated data.
np.random.seed(42)
n_samples = 1000

# Synthetic features: inlet_flow, outlet_flow, capacity, current_level_m, rate_percent, rate_mph, surface_area, current_level_percent
data = {
    "inlet_flow": np.random.uniform(0, 100, n_samples),   # in L/s (for example)
    "outlet_flow": np.random.uniform(0, 150, n_samples),    # in L/s
    "capacity": np.random.uniform(1e3, 1e5, n_samples),     # in m³
    "current_level_m": np.random.uniform(0.5, 10, n_samples),
    "rate_percent": np.random.uniform(-10, -0.1, n_samples),  # negative rate (%/hr) for draining
    "rate_mph": np.random.uniform(-1, -0.01, n_samples),     # negative rate (m/hr)
    "surface_area": np.random.uniform(50, 5000, n_samples), 
    "current_level_percent": np.random.uniform(10, 100, n_samples)
}

df = pd.DataFrame(data)

# For our target variable, we can use the net flow model (if outlet > inlet) as a simple approximation:
# We'll calculate a "true" retention time using the net flow equation if possible, and otherwise use a rate-of-change approach.
def compute_retention_time(row):
    # Convert flows from L/s to m³/s
    inlet = row["inlet_flow"] * 0.001
    outlet = row["outlet_flow"] * 0.001
    net_flow = outlet - inlet
    if net_flow > 0:
        return row["capacity"] / net_flow / 3600
    else:
        # Fallback: use rate_percent if available (assume full tank if current_level_percent missing)
        current_pct = row["current_level_percent"]
        return current_pct / abs(row["rate_percent"])

df["retention_time"] = df.apply(compute_retention_time, axis=1)

# Feature matrix X and target y
feature_columns = ["inlet_flow", "outlet_flow", "capacity", "current_level_m", "rate_percent", "rate_mph", "surface_area", "current_level_percent"]
X = df[feature_columns]
y = df["retention_time"]

# Train a Random Forest Regressor
rf = RandomForestRegressor(n_estimators=100, random_state=42)
rf.fit(X, y)

# Save the model
joblib.dump(rf, "rf_retention_model.pkl")
print("Model trained and saved as rf_retention_model.pkl")
