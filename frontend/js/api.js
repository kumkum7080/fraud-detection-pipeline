// API request wrappers and authentication manager

const API_BASE = "http://127.0.0.1:8000/api";

export const auth = {
    login: async (username, password) => {
        const params = new URLSearchParams();
        params.append("username", username);
        params.append("password", password);
        
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: params
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Authentication failed");
        }
        
        const data = await response.json();
        localStorage.setItem("fraud_token", data.access_token);
        return data;
    },
    
    logout: () => {
        localStorage.removeItem("fraud_token");
        window.location.href = "login.html?v=1.0.2";
    },
    
    getToken: () => {
        return localStorage.getItem("fraud_token");
    },
    
    getHeaders: () => {
        const token = localStorage.getItem("fraud_token");
        return {
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
        };
    },
    
    checkAuth: async () => {
        const token = localStorage.getItem("fraud_token");
        if (!token) {
            // Redirect to login if not already on login page
            if (!window.location.pathname.includes("login.html")) {
                window.location.href = "login.html?v=1.0.2";
            }
            return null;
        }
        
        try {
            const response = await fetch(`${API_BASE}/auth/me`, {
                headers: auth.getHeaders()
            });
            if (!response.ok) {
                auth.logout();
                return null;
            }
            const user = await response.json();
            // Cache user in localStorage
            localStorage.setItem("fraud_user", JSON.stringify(user));
            return user;
        } catch (e) {
            console.error("Auth check failed:", e);
            return null;
        }
    },
    
    getUser: () => {
        const userStr = localStorage.getItem("fraud_user");
        return userStr ? JSON.parse(userStr) : null;
    }
};

async function apiFetch(endpoint, options = {}) {
    const headers = auth.getHeaders();
    const config = {
        ...options,
        headers: {
            ...headers,
            ...options.headers
        }
    };
    
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    
    if (response.status === 401) {
        auth.logout();
        throw new Error("Session expired. Please re-authenticate.");
    }
    
    if (!response.ok) {
        let errMsg = "API Request failed";
        try {
            const err = await response.json();
            errMsg = err.detail || errMsg;
        } catch (e) {}
        throw new Error(errMsg);
    }
    
    if (response.status === 204) {
        return null;
    }
    
    return await response.json();
}

export const api = {
    // Transactions
    getTransactions: (params = {}) => {
        const urlParams = new URLSearchParams();
        if (params.limit) urlParams.append("limit", params.limit);
        if (params.skip) urlParams.append("skip", params.skip);
        if (params.customer_id) urlParams.append("customer_id", params.customer_id);
        if (params.only_flagged) urlParams.append("only_flagged", params.only_flagged);
        return apiFetch(`/transactions/?${urlParams.toString()}`);
    },
    
    // Alerts
    getAlerts: (status) => {
        const query = status ? `?status=${status}` : "";
        return apiFetch(`/alerts/${query}`);
    },
    
    getAlert: (id) => {
        return apiFetch(`/alerts/${id}`);
    },
    
    claimAlert: (id) => {
        return apiFetch(`/alerts/${id}/claim`, { method: "PUT" });
    },
    
    resolveAlert: (id, status, notes) => {
        return apiFetch(`/alerts/${id}/resolve`, {
            method: "PUT",
            body: JSON.stringify({ status, notes })
        });
    },
    
    // Rules
    getRules: () => {
        return apiFetch("/rules/");
    },
    
    createRule: (payload) => {
        return apiFetch("/rules/", {
            method: "POST",
            body: JSON.stringify(payload)
        });
    },
    
    updateRule: (id, payload) => {
        return apiFetch(`/rules/${id}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });
    },
    
    deleteRule: (id) => {
        return apiFetch(`/rules/${id}`, { method: "DELETE" });
    },
    
    // Analytics
    getMetrics: () => apiFetch("/analytics/metrics"),
    getScatter: () => apiFetch("/analytics/scatter"),
    getTrends: () => apiFetch("/analytics/trends"),
    getHistogram: () => apiFetch("/analytics/histogram"),
    
    // System controls
    getSystemStatus: () => apiFetch("/system/status"),
    retrainModel: () => apiFetch("/system/retrain", { method: "POST" }),
    startSimulation: () => apiFetch("/system/simulation/start", { method: "POST" }),
    stopSimulation: () => apiFetch("/system/simulation/stop", { method: "POST" })
};
