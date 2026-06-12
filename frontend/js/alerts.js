import { auth, api } from './api.js';

let currentFilterStatus = "";
let currentUser = null;

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Verify Authentication
    currentUser = await auth.checkAuth();
    if (!currentUser) return;

    document.getElementById("analyst-badge").textContent = `Analyst: ${currentUser.username} (${currentUser.role})`;
    document.getElementById("logout-btn").addEventListener("click", auth.logout);

    // 2. Load Alert incident queue table
    loadAlertQueue();

    // 3. Setup event listeners
    setupFilters();
    setupModalBindings();
});

function setupFilters() {
    const filterBtns = document.querySelectorAll(".filter-btn");
    filterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            filterBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            currentFilterStatus = btn.getAttribute("data-status");
            loadAlertQueue();
        });
    });
}

async function loadAlertQueue() {
    const tbody = document.getElementById("alerts-tbody");
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Fetching alerts queue...</td></tr>`;

    try {
        const alerts = await api.getAlerts(currentFilterStatus);
        
        if (!alerts.length) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No matching alerts found.</td></tr>`;
            return;
        }

        let html = "";
        alerts.forEach(alert => {
            const tx = alert.transaction || {};
            const analystName = alert.analyst ? alert.analyst.username : "Unassigned";
            
            // Format Timestamp
            const dateStr = new Date(alert.created_at).toLocaleString();
            
            // Build risk badge styling
            let riskBadgeClass = "badge-warning";
            if (alert.risk_score >= 85) riskBadgeClass = "badge-danger";
            else if (alert.risk_score < 70) riskBadgeClass = "badge-info";

            // Status badge styling
            let statusBadgeClass = "badge-info";
            if (alert.status === "OPEN") statusBadgeClass = "badge-danger";
            else if (alert.status === "UNDER_REVIEW") statusBadgeClass = "badge-warning";
            else if (alert.status.startsWith("RESOLVED")) statusBadgeClass = "badge-success";

            // Row click action parameter helper
            html += `
                <tr style="cursor: pointer;" class="alert-row" data-alert-id="${alert.id}">
                    <td style="font-family: var(--font-mono); font-weight:600;">#${alert.id}</td>
                    <td style="font-family: var(--font-mono); font-weight:600;">${alert.transaction_id}</td>
                    <td>${tx.customer_id || '---'}</td>
                    <td><span class="badge ${riskBadgeClass}">${alert.risk_score}% RISK</span></td>
                    <td><span class="badge ${statusBadgeClass}">${alert.status}</span></td>
                    <td style="font-weight: 500;">${analystName}</td>
                    <td>${dateStr}</td>
                    <td>
                        <button class="control-btn investigate-btn" style="padding: 0.25rem 0.50rem; font-size: 0.75rem;" data-alert-id="${alert.id}">
                            Investigate
                        </button>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;

        // Bind row clicks
        document.querySelectorAll(".alert-row").forEach(row => {
            row.addEventListener("click", (e) => {
                // If they clicked the action button specifically, let its event bubble or trigger same
                const id = row.getAttribute("data-alert-id");
                openInvestigationModal(id);
            });
        });

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-danger);">Failed to load alerts: ${e.message}</td></tr>`;
    }
}

let activeInvestigatingAlertId = null;

async function openInvestigationModal(alertId) {
    activeInvestigatingAlertId = alertId;
    const modal = document.getElementById("alert-modal");
    const mError = document.getElementById("modal-error");
    mError.style.display = "none";
    
    // Clear modal details temporarily
    document.getElementById("info-alert-id").textContent = "Loading...";
    document.getElementById("info-tx-id").textContent = "Loading...";
    document.getElementById("info-cust-id").textContent = "Loading...";
    document.getElementById("info-timestamp").textContent = "Loading...";
    document.getElementById("info-amount").textContent = "Loading...";
    document.getElementById("info-rolling-avg").textContent = "Loading...";
    document.getElementById("info-deviation").textContent = "Loading...";
    document.getElementById("info-velocity").textContent = "Loading...";
    document.getElementById("info-zips").textContent = "Loading...";
    document.getElementById("info-zip-mismatch").textContent = "Loading...";
    
    // Hide controls
    document.getElementById("modal-claim-btn").style.display = "none";
    document.getElementById("modal-submit-btn").style.display = "none";
    document.getElementById("resolution-form-section").style.display = "none";
    document.getElementById("resolution-view-section").style.display = "none";

    // Show modal backdrop
    modal.classList.add("show");

    try {
        const alert = await api.getAlert(alertId);
        const tx = alert.transaction || {};
        
        // Fill Profile details
        document.getElementById("info-alert-id").innerHTML = `#${alert.id} <span class="badge ${alert.risk_score >= 85 ? 'badge-danger' : 'badge-warning'}">${alert.risk_score}% RISK</span>`;
        document.getElementById("info-tx-id").textContent = alert.transaction_id;
        document.getElementById("info-cust-id").textContent = tx.customer_id || '---';
        document.getElementById("info-timestamp").textContent = new Date(alert.created_at).toLocaleString();
        
        // Fill Indicators
        document.getElementById("info-amount").textContent = `$${Number(tx.amount || 0).toFixed(2)}`;
        document.getElementById("info-rolling-avg").textContent = `$${Number(tx.rolling_avg_amount || 0).toFixed(2)}`;
        document.getElementById("info-deviation").textContent = `${tx.amount_deviation_ratio || 0}x baseline`;
        document.getElementById("info-velocity").textContent = `${tx.velocity_1h || 0} tx / hour`;
        document.getElementById("info-zips").textContent = `${tx.customer_zip} (Home) / ${tx.merchant_zip} (Merchant)`;
        
        const zipMismatch = tx.zip_mismatch === 1;
        const mismatchLabel = document.getElementById("info-zip-mismatch");
        mismatchLabel.textContent = zipMismatch ? "MISMATCH DETECTED" : "MATCHED";
        mismatchLabel.className = zipMismatch ? "badge badge-danger" : "badge badge-success";

        // Layout display logic based on status and claiming
        if (alert.status === "OPEN") {
            document.getElementById("modal-claim-btn").style.display = "block";
        } 
        else if (alert.status === "UNDER_REVIEW") {
            // Is it claimed by the current analyst?
            if (alert.analyst_id === currentUser.id) {
                document.getElementById("resolution-form-section").style.display = "block";
                document.getElementById("modal-submit-btn").style.display = "block";
                
                // Clear input defaults
                document.getElementById("resolve-status").value = "";
                document.getElementById("resolve-notes").value = "";
            } else {
                // Claimed by another analyst
                document.getElementById("resolution-view-section").style.display = "block";
                document.getElementById("view-resolve-status").innerHTML = `<span class="badge badge-warning">UNDER REVIEW</span> claimed by Analyst ID: ${alert.analyst_id}`;
                document.getElementById("view-resolve-notes").textContent = "Analyst is currently performing investigation audit. Controls locked.";
            }
        } 
        else {
            // Resolved states
            document.getElementById("resolution-view-section").style.display = "block";
            const decisionStr = alert.status === "RESOLVED_SAFE" ? "LEGITIMATE (Approved)" : "TRUE FRAUD (Declined & Frozen)";
            const decisionClass = alert.status === "RESOLVED_SAFE" ? "badge-success" : "badge-danger";
            
            document.getElementById("view-resolve-status").innerHTML = `<span class="badge ${decisionClass}">${decisionStr}</span> resolved by Analyst ID: ${alert.analyst_id || 'System'}`;
            document.getElementById("view-resolve-notes").textContent = alert.notes || "No resolution details submitted.";
        }

    } catch (e) {
        mError.textContent = "Error pulling details: " + e.message;
        mError.style.display = "block";
    }
}

function setupModalBindings() {
    const modal = document.getElementById("alert-modal");
    const closeBtn = document.getElementById("modal-close");
    const cancelBtn = document.getElementById("modal-cancel-btn");
    const claimBtn = document.getElementById("modal-claim-btn");
    const submitBtn = document.getElementById("modal-submit-btn");
    const mError = document.getElementById("modal-error");

    const closeModalFunc = () => {
        modal.classList.remove("show");
        activeInvestigatingAlertId = null;
    };

    closeBtn.addEventListener("click", closeModalFunc);
    cancelBtn.addEventListener("click", closeModalFunc);

    // Close on clicking backdrop
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModalFunc();
    });

    claimBtn.addEventListener("click", async () => {
        try {
            claimBtn.disabled = true;
            await api.claimAlert(activeInvestigatingAlertId);
            // Refresh modal state
            openInvestigationModal(activeInvestigatingAlertId);
            // Refresh queue behind it
            loadAlertQueue();
        } catch (e) {
            mError.textContent = "Failed to claim: " + e.message;
            mError.style.display = "block";
        } finally {
            claimBtn.disabled = false;
        }
    });

    submitBtn.addEventListener("click", async () => {
        const statusVal = document.getElementById("resolve-status").value;
        const notesVal = document.getElementById("resolve-notes").value;
        
        if (!statusVal) {
            mError.textContent = "Please select a resolution status.";
            mError.style.display = "block";
            return;
        }

        try {
            submitBtn.disabled = true;
            await api.resolveAlert(activeInvestigatingAlertId, statusVal, notesVal);
            closeModalFunc();
            loadAlertQueue();
        } catch (e) {
            mError.textContent = "Failed to submit resolution: " + e.message;
            mError.style.display = "block";
            submitBtn.disabled = false;
        }
    });
}
