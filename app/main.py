"""Main FastAPI application for AI Governance Platform"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routers import guardrails, enterprise, feedback, auth, conversations, demo_agent
from app.services.audit_service import get_audit_service
from app.services.enterprise_service import get_enterprise_service
from app.services.feedback_service import get_feedback_service
from app.services.auth_service import get_auth_service
from app.services.conversation_service import get_conversation_service
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="AI Governance Platform - Prototype for managing and monitoring AI agents",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
# Configure allowed origins based on environment
ALLOWED_ORIGINS = [
    "https://ai-governance-platform-902023244402.us-central1.run.app",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Include routers
app.include_router(guardrails.router)
app.include_router(enterprise.router)
app.include_router(feedback.router)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(demo_agent.router)

# Serve dashboard
DASHBOARD_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")


@app.get("/dashboard")
async def serve_dashboard():
    """Serve the dashboard HTML"""
    return FileResponse(os.path.join(DASHBOARD_PATH, "index.html"))


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting AI Governance Platform...")
    logger.info(f"Project ID: {settings.project_id}")
    logger.info(f"Gemini Model: {settings.gemini_model}")

    # Initialize BigQuery tables
    audit_service = get_audit_service()
    await audit_service.setup_bigquery_table()

    # Initialize enterprise tables
    enterprise_service = get_enterprise_service()
    await enterprise_service.setup_enterprise_tables()

    # Initialize feedback tables
    feedback_service = get_feedback_service()
    await feedback_service.setup_feedback_table()

    # Initialize auth/API keys tables
    auth_service = get_auth_service()
    await auth_service.setup_keys_table()

    # Initialize conversation tracking tables
    conversation_service = get_conversation_service()
    await conversation_service.setup_conversation_tables()

    logger.info("AI Governance Platform started successfully!")


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - returns API information"""
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        services={
            "gemini": "initialized",
            "bigquery": "initialized",
            "api": "running"
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        services={
            "api": "running",
            "gemini": "available",
            "audit": "available"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug
    )
