"""
Claudine Server v1 - Main Application
Clean Architecture implementation with FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.presentation.routers import health, auth

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    """Actions to perform on application startup."""
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"📍 API documentation available at /docs")
    print(f"🔧 Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event():
    """Actions to perform on application shutdown."""
    print(f"👋 {settings.APP_NAME} shutting down...")


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }
