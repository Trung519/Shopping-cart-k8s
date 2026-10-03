"""Real Uvicorn HTTP boundary: context, concurrent isolation and log privacy."""
import asyncio
import concurrent.futures
import io
import json
import logging
import os
import socket
import threading
import time
import unittest
import urllib.request
from contextlib import asynccontextmanager
from unittest.mock import patch

import uvicorn
from fastapi import APIRouter, FastAPI
from sqlalchemy import create_engine
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from product_catalog.telemetry import instrument, configure_access_logging


class AccessTraceAcceptance(unittest.TestCase):
    def test_uvicorn_included_router_and_concurrent_requests(self):
        @asynccontextmanager
        async def lifespan(app):
            configure_access_logging()
            yield

        app = FastAPI(lifespan=lifespan)
        router = APIRouter()

        @router.get('/products/{product_id}')
        async def read(product_id: str):
            await asyncio.sleep(0.015)
            return {'ok': True}

        app.include_router(router)
        exporter = InMemorySpanExporter()
        with patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://127.0.0.1:9', 'OTEL_TRACES_SAMPLER': 'always_on'}), patch('product_catalog.telemetry.OTLPSpanExporter', return_value=exporter):
            provider = instrument(app, create_engine('sqlite://'))
        output = io.StringIO()
        logger = logging.getLogger('uvicorn.access')
        handler = logging.StreamHandler(output)
        # Match production ordering: default Uvicorn config resets the logger,
        # then app startup must reapply correlation/JSON before serving requests.
        config = uvicorn.Config(app, lifespan='on')
        handler.setFormatter(logging.Formatter('%(message)s'))
        old_handlers = logger.handlers[:]
        logger.handlers = [handler]
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(config)
        worker = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(server.started)

            def request(n):
                tid = format(n + 1, '032x')
                req = urllib.request.Request(
                    f'http://127.0.0.1:{port}/products/item-{n}?secret=private-marker',
                    headers={'traceparent': f'00-{tid}-1234567890abcdef-01',
                             'Cookie': 'private-cookie', 'Authorization': 'Bearer private-token'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                return f'/products/item-{n}', tid

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                expected = dict(pool.map(request, range(8)))
            provider.force_flush()
            records = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(len(records), 8)
            spans = exporter.get_finished_spans()
            for record in records:
                self.assertEqual(record['trace_id'], expected[record['path']])
                self.assertEqual(record['status'], 200)
                self.assertEqual(record['method'], 'GET')
                self.assertTrue(any(format(s.context.trace_id, '032x') == record['trace_id'] and
                                    format(s.context.span_id, '016x') == record['span_id'] for s in spans))
            self.assertNotIn('private-', output.getvalue())
            self.assertNotIn('secret=', output.getvalue())
            self.assertEqual(len({r['trace_id'] for r in records}), 8)
        finally:
            server.should_exit = True
            worker.join(timeout=5)
            provider.shutdown()
            logger.handlers = old_handlers
            sock.close()


if __name__ == '__main__':
    unittest.main()
