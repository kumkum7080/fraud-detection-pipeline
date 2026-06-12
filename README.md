 Enterprise Fraud Detection & Risk Mitigation Platform

An end-to-end cyber-security data engineering and machine learning framework designed to isolate and mitigate financial anomaly signatures in real-time. 

This platform leverages **FastAPI** for high-frequency endpoints, **MySQL** as the persistent system of record, **Redis** for sub-millisecond sliding-window velocity tracking and baseline caching, and an unsupervised **Isolation Forest** machine learning model. The front-end is a clean, premium, bank-style Analyst Command Center built with **Vanilla HTML5, CSS3, and JavaScript**.

---

##  Key Features

* **Hybrid Scoring Engine**: Combines static heuristic rules (customizable weights) with a standard-scaled **Isolation Forest** ML model to output a combined risk index (0–100%) for every incoming transaction.
* **Analyst Command Center**: A professional, responsive, light-colored bank dashboard featuring:
  * Indicator panels showing total traffic, active alerts, baseline network risk, and recall accuracy.
  * Real-time scatter topographical chart (deviation ratio vs velocity) and decile risk score histograms using **Chart.js**.
  * Live-streaming transaction feed with instant desktop toast alarm notifications.
* **Heuristics Scoring Console (Rules Engine)**: Full CRUD console enabling administrators to dynamically add, edit, or delete static rules (e.g. transaction amount limits, zip code mismatch flags, velocity thresholds) and modify their risk weights.
* **Incident Response Queue (Alert System)**: Multi-state queue (`OPEN`, `UNDER_REVIEW`, `RESOLVED_SAFE`, `RESOLVED_FRAUD`) where analysts can claim alerts, document investigation findings, and approve/block transactions.
* **Interactive Ingestion Streamer**: Generates realistic randomized transaction telemetry streams (with velocity spikes and geographical variance anomalies) in the background to test scoring and alerts.
* **Graceful Degradation**: Features a custom in-memory mock client fallback for Redis, allowing the entire backend to run out-of-the-box even if a local Redis server is not running.

---

##  Repository Structure

```
fraud-detection-pipeline-main/
├── backend/
│   ├── app/
│   │   ├── routers/           # FastAPI routers (auth, alerts, analytics, rules, system, transactions)
│   │   ├── auth.py            # JWT Authentication & raw bcrypt verification
│   │   ├── config.py          # MySQL and Redis configurations
│   │   ├── crud.py            # MySQL database query layer
│   │   ├── database.py        # SQLAlchemy database engine
│   │   ├── ml_engine.py       # Isolation Forest scoring & standard scaling fit
│   │   ├── models.py          # SQLAlchemy models (Transaction, Alert, Rule, Analyst, AuditLog)
│   │   ├── redis_client.py    # Redis velocity tracker & Mock Client fallback
│   │   ├── rules_engine.py    # Rules compiler and risk score aggregator
│   │   ├── schemas.py         # Pydantic schemas for request validation
│   │   ├── seed.py            # Seeder: loads 2500 transactions, defaults rules, fits Isolation Forest
│   │   └── main.py            # FastAPI entry point
│   ├── requirements.txt       # Python package dependencies
│   └── test_api.py            # Backend integration test suite
├── frontend/                  # Vanilla HTML/CSS/JS Analyst Portal
│   ├── css/
│   │   └── bank-style.css     # Clean corporate light-theme stylesheet
│   ├── js/
│   │   ├── api.js             # API query wrappers and JWT session manager
│   │   ├── dashboard.js       # Chart.js loaders & telemetry bindings
│   │   ├── alerts.js          # Alert queue table and detailed investigation modal
│   │   └── rules.js           # Rules editor CRUD event handlers
│   ├── index.html             # Analyst Dashboard
│   ├── alerts.html            # Incident Queue Page
│   ├── rules.html             # Heuristics Scoring Manager
│   └── login.html             # Portal Login Page
└── README.md                  # System Documentation
```

---

##  Getting Started

### 1. Database Configuration
Ensure your local **MySQL** server is running. Create a database named `pricing_system` (or modify `backend/app/config.py` with your custom credentials).

### 2. Install Dependencies
Install the required packages for the FastAPI backend:
```powershell
pip install -r backend/requirements.txt
```

### 3. Initialize & Seed Database
Run the seed script to setup the schema, register analyst profiles (`admin` and `analyst`), generate 2,500 base transactions, and pre-train the Isolation Forest ML model:
```powershell
python backend/app/seed.py
```

### 4. Run the API Server
Start the Uvicorn ASGI server to host the backend:
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
*The API interactive documentation will be available at `http://127.0.0.1:8000/docs`.*

### 5. Run the Front-End Server
Serve the static front-end assets (run from the project root):
```powershell
python -m http.server 5500 --directory frontend --bind 127.0.0.1
```
Navigate to **`http://localhost:5500/login.html`** in your browser.

---

##  Default Credentials

To explore the portal, log in as either:

| Role | Username | Password |
| :--- | :--- | :--- |
| **Administrator** | `admin` | `admin` |
| **Analyst** | `analyst` | `analyst` |

*Note: Custom rules can only be created, updated, or deleted by users with the `ADMIN` role.*
