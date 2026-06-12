import { auth, api } from './api.js';

let scatterChart = null;
let histogramChart = null;
let pollInterval = null;
let knownAlerts = new Set();

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Verify Authentication
    const user = await auth.checkAuth();
    if (!user) return; // checkAuth handles redirects
    
    // Set analyst badge details
    document.getElementById("analyst-badge").textContent = `Analyst: ${user.username} (${user.role})`;
    document.getElementById("logout-btn").addEventListener("click", auth.logout);

    // 2. Initialize Telemetry Graphs
    initCharts();

    // 3. Load Static Data and Telemetry Bindings
    await refreshTelemetry();
    setupEventListeners();

    // 4. Start Live Telemetry Updates (Every 4 seconds)
    pollInterval = setInterval(refreshTelemetry, 4000);
});

function setupEventListeners() {
    const startSimBtn = document.getElementById("start-sim-btn");
    const stopSimBtn = document.getElementById("stop-sim-btn");
    const retrainBtn = document.getElementById("retrain-model-btn");

    startSimBtn.addEventListener("click", async () => {
        try {
            startSimBtn.disabled = true;
            await api.startSimulation();
            await refreshTelemetry();
        } catch (e) {
            alert("Simulator failed to start: " + e.message);
            startSimBtn.disabled = false;
        }
    });

    stopSimBtn.addEventListener("click", async () => {
        try {
            stopSimBtn.disabled = true;
            await api.stopSimulation();
            await refreshTelemetry();
        } catch (e) {
            alert("Simulator failed to stop: " + e.message);
            stopSimBtn.disabled = false;
        }
    });

    retrainBtn.addEventListener("click", async () => {
        try {
            retrainBtn.disabled = true;
            retrainBtn.textContent = "⚡ Retraining Engine...";
            await api.retrainModel();
            alert("Isolation Forest model retrained successfully!");
            await refreshTelemetry();
        } catch (e) {
            alert("Retraining failed: " + e.message);
        } finally {
            retrainBtn.disabled = false;
            retrainBtn.textContent = "⚡ Retrain Outlier Model";
        }
    });
}

async function refreshTelemetry() {
    try {
        // Fetch dashboard statistics
        const [metrics, system, scatterData, histogramData, alerts] = await Promise.all([
            api.getMetrics(),
            api.getSystemStatus(),
            api.getScatter(),
            api.getHistogram(),
            api.getAlerts("OPEN")
        ]);

        // 1. Update Indicators Panel
        document.getElementById("metric-traffic").textContent = Number(metrics.total_traffic).toLocaleString();
        document.getElementById("metric-alerts").textContent = metrics.active_alerts;
        document.getElementById("metric-risk").textContent = `${metrics.system_baseline_risk}%`;
        document.getElementById("metric-accuracy").textContent = `${metrics.engine_detection_accuracy}%`;

        // 2. Update Model Manager Status Card
        const statusText = document.getElementById("model-status-text");
        if (system.model_trained) {
            statusText.innerHTML = `Model status: <span class="badge badge-success">ACTIVE</span><br>Last Trained: <b>${system.model_last_trained}</b> (Rows: ${system.historical_tx_count})`;
        } else {
            statusText.innerHTML = `Model status: <span class="badge badge-warning">HEURISTICS FALLBACK</span><br>Seeding dataset required to fit Isolation Forest.`;
        }

        // Disable retrain button if less than 100 rows
        document.getElementById("retrain-model-btn").disabled = !system.can_retrain;

        // 3. Update Telemetry Simulator controls
        const simLabel = document.getElementById("sim-status-label");
        const startSimBtn = document.getElementById("start-sim-btn");
        const stopSimBtn = document.getElementById("stop-sim-btn");

        if (system.simulation_running) {
            simLabel.textContent = "STREAMING LIVE";
            simLabel.className = "badge badge-success";
            startSimBtn.disabled = true;
            stopSimBtn.disabled = false;
        } else {
            simLabel.textContent = "OFFLINE";
            simLabel.className = "badge badge-info";
            startSimBtn.disabled = false;
            stopSimBtn.disabled = true;
        }

        // 4. Render Chart datasets
        updateScatterChart(scatterData);
        updateHistogramChart(histogramData);

        // 5. Update Alert incident table & raise alarms for new alerts
        updateAlertFeedTable(alerts);

    } catch (e) {
        console.error("Telemetry refresh failed:", e);
    }
}

function initCharts() {
    // A. Initialize Scatter Chart
    const ctxScatter = document.getElementById('scatterChart').getContext('2d');
    scatterChart = new Chart(ctxScatter, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Normal Traffic',
                    data: [],
                    backgroundColor: 'rgba(16, 185, 129, 0.4)', // transparent green
                    borderColor: '#10b981',
                    borderWidth: 1,
                    pointRadius: 4
                },
                {
                    label: 'Isolated Outliers',
                    data: [],
                    backgroundColor: 'rgba(244, 63, 94, 0.8)', // solid rose red
                    borderColor: '#f43f5e',
                    borderWidth: 1.5,
                    pointRadius: 6,
                    showLine: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Spending Deviation Ratio', color: '#475569' },
                    grid: { color: 'rgba(15, 23, 42, 0.06)' },
                    ticks: { color: '#64748b' }
                },
                y: {
                    title: { display: true, text: '1-Hour Spending Velocity', color: '#475569' },
                    grid: { color: 'rgba(15, 23, 42, 0.06)' },
                    ticks: { color: '#64748b' }
                }
            },
            plugins: {
                legend: { labels: { color: '#0f172a' } }
            }
        }
    });

    // B. Initialize Histogram Chart
    const ctxHist = document.getElementById('histogramChart').getContext('2d');
    histogramChart = new Chart(ctxHist, {
        type: 'bar',
        data: {
            labels: ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'],
            datasets: [
                {
                    label: 'Legitimate',
                    data: [],
                    backgroundColor: 'rgba(59, 130, 246, 0.75)', // Blue
                    borderColor: '#3b82f6',
                    borderWidth: 1
                },
                {
                    label: 'True Fraud',
                    data: [],
                    backgroundColor: 'rgba(244, 63, 94, 0.85)', // Red
                    borderColor: '#f43f5e',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Calculated Risk Factor (%)', color: '#475569' },
                    grid: { color: 'rgba(15, 23, 42, 0.06)' },
                    ticks: { color: '#64748b' }
                },
                y: {
                    title: { display: true, text: 'Frequency Count', color: '#475569' },
                    grid: { color: 'rgba(15, 23, 42, 0.06)' },
                    ticks: { color: '#64748b' }
                }
            },
            plugins: {
                legend: { labels: { color: '#0f172a' } }
            }
        }
    });
}

function updateScatterChart(data) {
    if (!scatterChart) return;
    
    const normal = [];
    const outliers = [];

    data.forEach(pt => {
        // Map fields to x and y coordinates
        const point = { x: pt.amount_deviation_ratio, y: pt.velocity_1h, id: pt.transaction_id };
        if (pt.ml_predicted_anomaly === 1 || pt.risk_score >= 70) {
            outliers.push(point);
        } else {
            normal.push(point);
        }
    });

    scatterChart.data.datasets[0].data = normal;
    scatterChart.data.datasets[1].data = outliers;
    scatterChart.update('none'); // silent update without animation lag
}

function updateHistogramChart(data) {
    if (!histogramChart) return;
    
    // Sort array by bucket ascending
    const sortedData = [...data].sort((a, b) => a.bucket - b.bucket);
    
    const legitimate = sortedData.map(d => d.non_fraud_count);
    const fraud = sortedData.map(d => d.fraud_count);
    
    histogramChart.data.datasets[0].data = legitimate;
    histogramChart.data.datasets[1].data = fraud;
    histogramChart.update('none');
}

function updateAlertFeedTable(alerts) {
    const tbody = document.getElementById("live-alerts-tbody");
    if (!alerts.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No active OPEN alerts in incident queue.</td></tr>`;
        return;
    }

    // Capture newest alerts to show alert Toast alarm notifications
    let isInitialLoad = (knownAlerts.size === 0);
    
    let html = "";
    // Only display top 5 highest risk alerts in feed
    const displayAlerts = alerts.slice(0, 5);
    
    displayAlerts.forEach(alert => {
        const tx = alert.transaction || {};
        
        // Register alert ID
        if (!knownAlerts.has(alert.id)) {
            knownAlerts.add(alert.id);
            if (!isInitialLoad) {
                // Play notification alarm sound or show Toast message
                showToastNotification(alert);
            }
        }

        html += `
            <tr>
                <td style="font-family: var(--font-mono); font-weight: 600;">${alert.transaction_id}</td>
                <td>${tx.customer_id || '---'}</td>
                <td style="font-weight: 600;">$${Number(tx.amount || 0).toFixed(2)}</td>
                <td>${tx.velocity_1h || 0} tx</td>
                <td>${tx.amount_deviation_ratio || 0}x</td>
                <td>
                    <span class="badge ${alert.risk_score >= 85 ? 'badge-danger' : 'badge-warning'}">
                        ${alert.risk_score}% RISK
                    </span>
                </td>
                <td><span class="badge badge-info">${alert.status}</span></td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

function showToastNotification(alert) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
        <div style="font-size: 1.5rem;">🚨</div>
        <div style="flex-grow: 1;">
            <div style="font-weight: 700; color: var(--color-danger);">CRITICAL ALERT DETECTED</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                TX ID: ${alert.transaction_id} (Customer Risk: ${alert.risk_score}%)
            </div>
        </div>
        <button style="background:transparent; border:none; color:white; cursor:pointer;" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove toast after 6 seconds
    setTimeout(() => {
        toast.remove();
    }, 6000);
}
