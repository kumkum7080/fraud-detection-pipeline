import { auth, api } from './api.js';

let currentUser = null;
let editingRuleId = null;

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Verify Authentication
    currentUser = await auth.checkAuth();
    if (!currentUser) return;

    document.getElementById("analyst-badge").textContent = `Analyst: ${currentUser.username} (${currentUser.role})`;
    document.getElementById("logout-btn").addEventListener("click", auth.logout);

    // Configure role-based views
    const isAdmin = currentUser.role === "ADMIN";
    if (isAdmin) {
        document.getElementById("create-rule-btn").style.display = "block";
    } else {
        document.getElementById("role-warning-badge").style.display = "inline-flex";
    }

    // 2. Load Rules grid
    loadRules();

    // 3. Setup event listeners
    setupModalBindings();
});

async function loadRules() {
    const container = document.getElementById("rules-container");
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem 0;">Fetching rules registry...</div>`;

    try {
        const rules = await api.getRules();
        
        if (!rules.length) {
            container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem 0;">No heuristics rules defined in engine database.</div>`;
            return;
        }

        const isAdmin = currentUser.role === "ADMIN";
        let html = "";
        
        rules.forEach(rule => {
            const statusClass = rule.is_active ? "badge-success" : "badge-danger";
            const statusText = rule.is_active ? "Active" : "Disabled";
            const modifierPrefix = rule.risk_modifier >= 0 ? "+" : "";

            // Format logical formula e.g. amount > 2500
            const logicalFormula = `${rule.field_name} ${rule.operator} ${rule.threshold_value}`;

            html += `
                <div class="rule-item-card">
                    <div style="flex-grow: 1;">
                        <div class="rule-header">
                            <span class="rule-name">${rule.name}</span>
                            <span class="badge ${statusClass}">${statusText}</span>
                        </div>
                        <p class="rule-desc">${rule.description || 'No description provided.'}</p>
                        <div class="rule-formula">${logicalFormula}</div>
                        <div class="rule-modifier">
                            <span style="color: var(--text-secondary);">Risk Modification:</span>
                            <span style="font-weight: 700; color: ${rule.risk_modifier >= 0 ? 'var(--color-danger)' : 'var(--color-success)'}">
                                ${modifierPrefix}${rule.risk_modifier} points
                            </span>
                        </div>
                    </div>
                    
                    ${isAdmin ? `
                        <div class="rule-actions">
                            <button class="control-btn edit-rule-btn" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" data-rule-id="${rule.id}">
                                Edit
                            </button>
                            <button class="control-btn btn-danger delete-rule-btn" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" data-rule-id="${rule.id}">
                                Delete
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        container.innerHTML = html;

        // Bind Edit/Delete click events
        if (isAdmin) {
            document.querySelectorAll(".edit-rule-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const id = btn.getAttribute("data-rule-id");
                    openEditRuleModal(id, rules);
                });
            });

            document.querySelectorAll(".delete-rule-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const id = btn.getAttribute("data-rule-id");
                    handleDeleteRule(id);
                });
            });
        }

    } catch (e) {
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--color-danger); padding: 3rem 0;">Failed to load rules: ${e.message}</div>`;
    }
}

function openEditRuleModal(ruleId, rulesList) {
    editingRuleId = ruleId;
    const rule = rulesList.find(r => r.id == ruleId);
    if (!rule) return;

    document.getElementById("modal-rule-title").textContent = "Modify Scoring Rule";
    document.getElementById("rule-id-input").value = rule.id;
    document.getElementById("rule-name").value = rule.name;
    document.getElementById("rule-desc").value = rule.description || "";
    document.getElementById("rule-field").value = rule.field_name;
    document.getElementById("rule-operator").value = rule.operator;
    document.getElementById("rule-threshold").value = rule.threshold_value;
    document.getElementById("rule-modifier").value = rule.risk_modifier;
    document.getElementById("rule-active").checked = rule.is_active;

    const modal = document.getElementById("rule-modal");
    document.getElementById("rule-modal-error").style.display = "none";
    modal.classList.add("show");
}

async function handleDeleteRule(ruleId) {
    if (!confirm("Are you sure you want to delete this scoring rule permanently?")) {
        return;
    }

    try {
        await api.deleteRule(ruleId);
        loadRules();
    } catch (e) {
        alert("Failed to delete rule: " + e.message);
    }
}

function setupModalBindings() {
    const modal = document.getElementById("rule-modal");
    const createBtn = document.getElementById("create-rule-btn");
    const closeBtn = document.getElementById("rule-modal-close");
    const cancelBtn = document.getElementById("rule-modal-cancel");
    const form = document.getElementById("rule-form");
    const mError = document.getElementById("rule-modal-error");

    const closeModalFunc = () => {
        modal.classList.remove("show");
        editingRuleId = null;
        form.reset();
    };

    if (createBtn) {
        createBtn.addEventListener("click", () => {
            editingRuleId = null;
            document.getElementById("modal-rule-title").textContent = "Create Scoring Rule";
            document.getElementById("rule-id-input").value = "";
            mError.style.display = "none";
            modal.classList.add("show");
        });
    }

    closeBtn.addEventListener("click", closeModalFunc);
    cancelBtn.addEventListener("click", closeModalFunc);

    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModalFunc();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        mError.style.display = "none";

        const payload = {
            name: document.getElementById("rule-name").value,
            description: document.getElementById("rule-desc").value,
            field_name: document.getElementById("rule-field").value,
            operator: document.getElementById("rule-operator").value,
            threshold_value: parseFloat(document.getElementById("rule-threshold").value),
            risk_modifier: parseFloat(document.getElementById("rule-modifier").value),
            is_active: document.getElementById("rule-active").checked
        };

        try {
            if (editingRuleId) {
                await api.updateRule(editingRuleId, payload);
            } else {
                await api.createRule(payload);
            }
            closeModalFunc();
            loadRules();
        } catch (err) {
            mError.textContent = err.message;
            mError.style.display = "block";
        }
    });
}
