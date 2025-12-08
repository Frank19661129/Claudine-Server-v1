"""
Claudine Server v1 - Main Application
Clean Architecture implementation with FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.presentation.routers import health, auth, calendar, conversation, monitor, persons, tasks, notes, inbox, mcp
import time

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS - Secure configuration for development/production
# Allows:
# - localhost with any port (development)
# - 127.0.0.1 with any port (development)
# - Tailscale IPs (100.x.x.x) with any port (remote access)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(http://localhost:\d+|http://127\.0\.0\.1:\d+|https?://100\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?)$",
    allow_credentials=False,  # We use JWT tokens in headers, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Test mode middleware - reads X-Test-Mode header and sets context
@app.middleware("http")
async def test_mode_middleware(request: Request, call_next):
    """Set test mode from X-Test-Mode header."""
    from app.core.test_mode_context import set_test_mode

    test_mode_header = request.headers.get("x-test-mode", "0")
    try:
        test_mode = int(test_mode_header)
        if test_mode in (0, 1, 2):
            set_test_mode(test_mode)
    except ValueError:
        pass  # Keep default of 0

    return await call_next(request)


# Request monitoring middleware
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Log all API requests to the monitor."""
    start_time = time.time()

    # Skip health check and monitor endpoints to avoid noise
    skip_paths = ["/api/v1/health", "/api/v1/monitor/transactions", "/api/v1/auth/upload-photo"]
    should_log = request.url.path not in skip_paths

    # Capture request body (skip multipart/form-data for file uploads)
    request_body = None
    content_type = request.headers.get("content-type", "")
    if should_log and request.method in ["POST", "PUT", "PATCH"] and "multipart/form-data" not in content_type:
        try:
            import json
            from starlette.datastructures import Headers

            body_bytes = await request.body()
            if body_bytes:
                request_body = json.loads(body_bytes.decode('utf-8'))

            # Create a new request with the body so endpoint can read it again
            async def receive():
                return {"type": "http.request", "body": body_bytes}

            request = Request(request.scope, receive)
        except:
            request_body = None

    try:
        response = await call_next(request)

        if should_log:
            duration_ms = int((time.time() - start_time) * 1000)
            status = "success" if response.status_code < 400 else "failure"

            # Extract user_id from auth header if available
            user_id = None
            try:
                from app.infrastructure.services.jwt import extract_user_id_from_token
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "")
                    user_id = extract_user_id_from_token(token)
            except:
                pass

            monitor.log_transaction(
                method=request.method,
                endpoint=request.url.path,
                status=status,
                status_code=response.status_code,
                duration=duration_ms,
                user_id=str(user_id) if user_id else None,
                request_body=request_body,
            )

        return response

    except Exception as e:
        if should_log:
            duration_ms = int((time.time() - start_time) * 1000)
            monitor.log_transaction(
                method=request.method,
                endpoint=request.url.path,
                status="failure",
                status_code=500,
                duration=duration_ms,
                error=str(e),
                request_body=request_body,
            )
        raise


# Include routers
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(calendar.router, prefix=settings.API_V1_PREFIX)
app.include_router(conversation.router, prefix=settings.API_V1_PREFIX)
app.include_router(persons.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router, prefix=settings.API_V1_PREFIX)
app.include_router(notes.router, prefix=settings.API_V1_PREFIX)
app.include_router(inbox.router, prefix=settings.API_V1_PREFIX)
app.include_router(mcp.router, prefix=settings.API_V1_PREFIX)
app.include_router(monitor.router, prefix=settings.API_V1_PREFIX)


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
