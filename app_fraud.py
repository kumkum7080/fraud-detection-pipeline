import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Dashboard Layout Setup
st.set_page_config(page_title="Fraud Detection Command Center", layout="wide")
st.title("🛡️ Enterprise Fraud Detection & Risk Mitigation Pipeline")
st.markdown("Real-time behavioral threat monitoring powered by an **Isolation Forest** anomaly engine and **MySQL** baseline extraction.")

# 2. Load Evaluated Data
df = pd.read_csv('evaluated_fraud_transactions.csv')

# 3. SIDEBAR ALERT FILTERING
st.sidebar.header("🚨 Threat Control Deck")
min_risk = st.sidebar.slider("Minimum Risk Score Alert Filter (%)", 0, 100, 75)

# Separate flagged alerts based on user threshold selection
alerts_df = df[df['risk_score_%'] >= min_risk].sort_values(by='risk_score_%', ascending=False)

# 4. HIGH-LEVEL CYBER METRICS
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Monitored Traffic", f"{len(df):,}")
col2.metric("Active System Alerts", len(alerts_df), delta=f"{len(alerts_df)} critical flagged", delta_color="inverse")
avg_risk = df['risk_score_%'].mean()
col3.metric("System Baseline Risk Index", f"{avg_risk:.1f}%")

caught_fraud = df[(df['ml_predicted_anomaly'] == 1) & (df['actual_ground_truth_fraud'] == 1)]
total_actual_fraud = df[df['actual_ground_truth_fraud'] == 1]
capture_rate = (len(caught_fraud) / len(total_actual_fraud) * 100) if len(total_actual_fraud) > 0 else 100
col4.metric("Engine Detection Accuracy", f"{capture_rate:.1f}%")

st.markdown("---")
st.subheader("📋 Live Real-Time Risk Incident Response Queue")
st.markdown("The high-risk accounts below have bypassed static rules and triggered behavioral heuristics flags.")
st.dataframe(
    alerts_df[['transaction_id', 'customer_id', 'timestamp', 'amount', 'velocity_1h', 'amount_deviation_ratio', 'risk_score_%']],
    use_container_width=True, hide_index=True
)

st.markdown("---")
st.subheader("🕵️ Deep Diagnostics Threat Vector Plots")
left_pane, right_pane = st.columns(2)

with left_pane:
    st.markdown("**Behavioral Outliers Mapping (Spending Deviation vs Velocity)**")
    fig_scatter = px.scatter(
        df, x="amount_deviation_ratio", y="velocity_1h",
        color="ml_predicted_anomaly", size="amount",
        color_discrete_sequence=["#22C55E", "#EF4444"],
        labels={"amount_deviation_ratio": "Spending Deviation Ratio", "velocity_1h": "1-Hour Tx Velocity", "ml_predicted_anomaly": "Is Outlier"},
        title="Threat Topography: Isolated Outliers"
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with right_pane:
    st.markdown("**Systemic Risk Distribution Wave**")
    fig_hist = px.histogram(
        df, x="risk_score_%", color="actual_ground_truth_fraud",
        color_discrete_sequence=["#3B82F6", "#DC2626"],
        labels={"risk_score_%": "Calculated Risk Factor", "actual_ground_truth_fraud": "True Fraud Status"},
        title="Risk Score Frequency Spectrum (Separation Efficiency)"
    )
    st.plotly_chart(fig_hist, use_container_width=True)
