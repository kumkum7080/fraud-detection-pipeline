from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.app.config import settings
from backend.app.database import engine, Base
from backend.app.ml_engine import MLEngine
from backend.app.routers import auth, transactions, alerts, rules, analytics, system

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A real-time cybersecurity telemetry backend featuring hybrid heuristic rules and scikit-learn Isolation Forest ML outlier detection.",
    version="1.0.0"
)

# Configure CORS Middleware
# Allows frontends running on live servers (e.g. localhost:5500, localhost:3000) or local file systems to query the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production environments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load machine learning model on startup
@app.on_event("startup")
def startup_event():
    print("[STARTUP] System Startup: Verifying model status...")
    # Attempt to load, if not trained, it will fallback gracefully
    loaded = MLEngine.load_model()
    if not loaded:
        print("[WARNING] System Startup: Trained model joblib not found. Run seeder/training command to activate ML outlier detection.")

# Include Endpoint Routers
app.include_router(auth.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(system.router, prefix="/api")

# Base Route
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs"
    }
