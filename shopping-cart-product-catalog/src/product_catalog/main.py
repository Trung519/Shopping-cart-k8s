"""Main FastAPI application for Product Catalog service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from .config import get_settings
from .database import engine, init_db
from .order_consumer import OrderCreatedConsumer
from .routers import health, products
from .security import setup_security
from .telemetry import configure_access_logging, instrument

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Uvicorn config can reset handlers after the module is imported by its CLI.
    # Configure again at startup, after server logging config has been applied.
    configure_access_logging()
    logger.info("starting_application", environment=settings.environment)

    # Initialize database
    try:
        init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise

    order_consumer = OrderCreatedConsumer()
    order_consumer.start()

    try:
        yield
    finally:
        order_consumer.stop()
        if telemetry_provider is not None:
            telemetry_provider.shutdown()

    logger.info("shutting_down_application")


app = FastAPI(
    title="Product Catalog Service",
    description="Product catalog microservice for Shopping Cart platform",
    version="1.1.0",
    lifespan=lifespan,
)

# Setup security middleware (rate limiting, security headers)
setup_security(app)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
telemetry_provider = instrument(app, engine)


def main() -> None:
    """Run the application."""
    import uvicorn

    uvicorn.run(
        "product_catalog.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
