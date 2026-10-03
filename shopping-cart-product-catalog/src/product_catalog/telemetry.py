"""Tracing for HTTP and SQLAlchemy, configured only through OTEL_* variables."""

import json
import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

request_logger = logging.getLogger("product_catalog.telemetry")
request_logger.setLevel(logging.INFO)
if not request_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    request_logger.addHandler(handler)
request_logger.propagate = False


class AccessTraceFilter(logging.Filter):
    """Capture context synchronously when Uvicorn emits the access record."""

    def filter(self, record):
        context = trace.get_current_span().get_span_context()
        record.trace_id = format(context.trace_id, "032x") if context.is_valid else None
        record.span_id = format(context.span_id, "016x") if context.is_valid else None
        return True


class AccessJSONFormatter(logging.Formatter):
    def format(self, record):
        # Uvicorn's access arguments: client, method, path+query, version, status.
        # Do not serialize the original message/client or arbitrary extra fields.
        if not isinstance(record.args, tuple) or len(record.args) != 5:
            return json.dumps({"event": "http_access", "service": "product-catalog",
                               "level": record.levelname.lower()})
        _, method, path, _, status = record.args
        data = {"event": "http_access", "service": "product-catalog",
                "level": record.levelname.lower(), "method": method,
                "path": path.split("?", 1)[0], "status": int(status)}
        if getattr(record, "trace_id", None):
            data.update(trace_id=record.trace_id, span_id=record.span_id)
        return json.dumps(data)


def configure_access_logging():
    logger = logging.getLogger("uvicorn.access")
    logger.setLevel(logging.INFO)
    if not any(isinstance(f, AccessTraceFilter) for f in logger.filters):
        logger.addFilter(AccessTraceFilter())
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    for handler in logger.handlers:
        handler.setFormatter(AccessJSONFormatter())
    logger.propagate = False


def instrument(app, engine):
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true" or not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    provider = TracerProvider(resource=Resource.create(), sampler=ALWAYS_ON if os.getenv("OTEL_TRACES_SAMPLER") == "always_on" else ParentBased(ALWAYS_ON))
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(timeout=5), max_queue_size=512,
        max_export_batch_size=128, schedule_delay_millis=1000,
    ))
    trace.set_tracer_provider(provider)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)

    def response_hook(span, scope, message):
        if message.get("type") != "http.response.start":
            return
        context = span.get_span_context()
        # No headers, URL query, body, SQL parameters or identity in this log.
        request_logger.info(json.dumps({
            "event": "http_request_completed", "service": "product-catalog",
            "level": "info",
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
            "method": scope.get("method"), "status": message.get("status"),
        }))

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="/health,/ready,/metrics",
        client_response_hook=response_hook,
    )
    configure_access_logging()
    return provider
