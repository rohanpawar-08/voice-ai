import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from config import settings
from routers import ws_copilot, actions_dev
from agent.tools import get_all_appointments
from app.core.database import check_db_health

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("copilot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Redis and check DB connection
    logger.info("Initializing VoiceDesk AI backend service...")
    try:
        r = await ws_copilot.get_redis_client()
        pong = await r.ping()
        logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} (ping: {pong})")
    except Exception as e:
        logger.warning(f"Could not connect to Redis at startup ({e}). Ensure Docker Redis container is running.")

    try:
        db_ok = await check_db_health()
        if db_ok:
            logger.info("Connected to PostgreSQL database successfully.")
        else:
            logger.warning("PostgreSQL database is currently unreachable. Ensure Docker PostgreSQL container is running.")
    except Exception as e:
        logger.warning(f"Database check exception at startup: {e}")

    yield
    # Shutdown: Clean up Redis connections
    logger.info("Shutting down VoiceDesk AI backend service...")
    if ws_copilot.redis_client is not None:
        await ws_copilot.redis_client.close()
        logger.info("Closed Redis connection pool.")


app = FastAPI(
    title="VoiceDesk AI - Omnichannel AI Voice Action Platform",
    version=settings.VERSION,
    description="India-first multilingual Voice Action Platform for Natural Speech Business Operations",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ws_copilot.router)
app.include_router(actions_dev.router)


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "VoiceDesk AI - Multilingual Voice Action Engine",
        "version": settings.VERSION,
        "active_adapter": "healthcare (Sai Smile Dental Clinic)",
        "websocket_endpoint": "/ws/copilot/{session_id}",
        "admin_api": "/api/appointments"
    }


@app.get("/health")
async def health_check():
    redis_healthy = False
    redis_details = "Not connected"
    try:
        r = await ws_copilot.get_redis_client()
        if await r.ping():
            redis_healthy = True
            redis_details = "Connected"
    except Exception as e:
        redis_details = str(e)

    db_healthy = False
    try:
        db_healthy = await check_db_health()
    except Exception:
        db_healthy = False

    is_overall_healthy = redis_healthy and db_healthy

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "database": {
            "postgres": "Connected" if db_healthy else "Disconnected/Unreachable",
        },
        "redis": {
            "status": redis_details,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT
        }
    }


# =========================================================================
# CLINIC ADMIN REST APIS
# =========================================================================

@app.get("/api/appointments")
async def get_clinic_appointments():
    """
    Returns list of all booked clinic appointments from Redis/memory
    for the Business Admin Panel.
    """
    appointments = get_all_appointments()
    return {
        "status": "success",
        "total": len(appointments),
        "appointments": appointments
    }


@app.delete("/api/appointments")
async def clear_clinic_appointments():
    """Clears all booked appointments from Redis for reset/testing."""
    try:
        r = await ws_copilot.get_redis_client()
        await r.delete("clinic:appointments")
        return {"status": "success", "message": "Cleared clinic appointments from Redis"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
