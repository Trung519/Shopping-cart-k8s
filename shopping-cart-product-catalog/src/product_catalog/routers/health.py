"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    rabbitmq: str = "not_configured"


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    details: dict[str, str]


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Basic health check."""
    # Check database
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    status = "healthy" if db_status == "healthy" else "unhealthy"

    return HealthResponse(status=status, database=db_status)


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(db: Session = Depends(get_db)) -> ReadinessResponse:
    """Readiness check for Kubernetes."""
    details: dict[str, str] = {}

    # Check database
    try:
        db.execute(text("SELECT 1"))
        details["database"] = "ready"
    except Exception as e:
        details["database"] = f"not_ready: {str(e)}"

    ready = all(v == "ready" for v in details.values())

    return ReadinessResponse(ready=ready, details=details)


@router.get("/live")
def liveness_check() -> dict[str, str]:
    """Liveness check for Kubernetes."""
    return {"status": "alive"}
