"""Tracing for HTTP and SQLAlchemy, configured only through OTEL_* variables."""

import json
import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
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
    return provider
