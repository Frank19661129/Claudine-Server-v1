"""
Health check router.
Part of Presentation layer.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    Returns server status and version.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/db")
async def database_health_check(db: Session = Depends(get_db)):
    """
    Database health check endpoint.
    Verifies database connectivity.
    """
    try:
        # Execute a simple query to test connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "service": settings.APP_NAME,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "service": settings.APP_NAME,
        }
