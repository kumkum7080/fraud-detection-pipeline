# Enterprise Fraud Detection & Risk Mitigation Pipeline

An end-to-end cyber-security data engineering and machine learning framework designed to isolate financial anomaly signatures. This multi-tiered software architecture leverages **MySQL** for high-frequency behavioral baseline window aggregations, fits an unsupervised **Isolation Forest** outlier matrix model, and drops real-time transaction risks onto an interactive **Streamlit Executive Analytics Command Center**.

---

## Key Architectural Pillars

* **Data Stream Automation:** Synthesizes a financial ledger logging transactional behavior vectors, while engineering distinct anomaly configurations (velocity spikes, geographic variance, structural spending outliers).
* **Database Optimization Engine (MySQL):** Runs complex temporal calculations utilizing analytical window frames (`AVG() OVER()`), spatial tracking flags (`CASE WHEN`), and interval velocity calculation to dynamically model baseline profiles into a clean Database View.
* **Unsupervised Machine Learning Framework:** Drops standard scalar metrics into an Isolation Forest engine, scoring transaction risk indicators dynamically on a localized 0-100% anomaly spectrum.
* **Incident Management UI:** Surges high-risk incident transactions onto a real-time responsive Streamlit analytical dashboard featuring modular threat maps and visual tracking waves.

---

## Repository Mapping

* `pipeline.py`: Comprehensive computational core running pipeline initialization, database staging, custom SQL feature extraction, and ML evaluation models.
* `app_fraud.py`: Front-end command configuration dashboard orchestrating operational risk tracking views.
* `requirements.txt`: Unified Python environment package dependencies mapping.

---

## Execution Protocol
* To run this project, first configure your environment by running the command "pip install -r requirements.txt" in your terminal. Next, ensure a native MySQL server instance is running locally on your computer with the database "pricing_system" initiated, and then execute the data pipeline engine by running the command "python pipeline.py". Finally, launch your interactive Streamlit analytics dashboard interface in your browser by running the command "streamlit run app_fraud.py".

