import logging
import os

from fastapi import FastAPI
from sqlalchemy.engine import Engine

# -----------------------------------------------------------------------------
# OpenTelemetry tracing (telemetry.py)
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

def setup_telemetry(app: FastAPI, engine: Engine) -> bool:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False

    # Tracing must never stop the API from starting, so any failure here is logged and ignored
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "saiv-backend")}), shutdown_on_exit=False)
        
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"), timeout=3)
        provider.add_span_processor(BatchSpanProcessor(exporter, export_timeout_millis=3000))
        trace.set_tracer_provider(provider)

        # Health checks and Prometheus scrapes would only add noise to the traces
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="health,metrics")
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
        return True
    except Exception:
        logger.exception("OpenTelemetry setup failed; continuing without tracing")
        return False
