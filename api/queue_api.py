"""
Sentinel FastAPI application.

Main entry point for the REST API.
Run with: uvicorn api.queue_api:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel_app import FraudTriageService
from api.routes import create_router


# Initialize the fraud triage service
service = FraudTriageService()

# Create FastAPI app
app = FastAPI(
    title="Sentinel Fraud Agent",
    version="0.8.0",
    description=(
        "Policy-controlled fraud investigation agent."
    ),
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(create_router(service))


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sentinel Fraud Investigation Agent",
        "docs": "/docs",
    }
