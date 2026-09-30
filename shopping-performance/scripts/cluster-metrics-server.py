#!/usr/bin/env python3
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ACTIVE_RUN = Path('/work/.local/active-run.json')
CONTEXT = 'k3d-lab-k8s'

def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def labels():
    try:
        value = json.loads(ACTIVE_RUN.read_text())
        return value.get('runId', 'idle'), value.get('profile', 'idle')
    except (OSError, ValueError):
        return 'idle', 'idle'

def collect():
    run_id, profile = labels()
    pods = json.loads(command('kubectl', '--context', CONTEXT, '-n', 'shopping-cart-apps', 'get', 'pods', '-o', 'json'))['items']
    active = [pod for pod in pods if not pod['metadata'].get('deletionTimestamp')]
    ready = sum(1 for pod in active if pod.get('status', {}).get('phase') == 'Running' and all(item.get('ready') for item in pod.get('status', {}).get('containerStatuses', [])))
    restarts = sum(item.get('restartCount', 0) for pod in active for item in pod.get('status', {}).get('containerStatuses', []))
    escaped_run = run_id.replace('"', '')
    escaped_profile = profile.replace('"', '')
    metric_labels = f'run_id="{escaped_run}",profile="{escaped_profile}"'
    return '\n'.join([
        '# HELP shopcart_app_ready_pods Ready ShopCart application pods.',
        '# TYPE shopcart_app_ready_pods gauge',
        f'shopcart_app_ready_pods{{{metric_labels}}} {ready}',
        '# HELP shopcart_app_total_pods Total ShopCart application pods.',
        '# TYPE shopcart_app_total_pods gauge',
        f'shopcart_app_total_pods{{{metric_labels}}} {len(active)}',
        '# HELP shopcart_app_restarts_total Cumulative ShopCart container restarts.',
        '# TYPE shopcart_app_restarts_total gauge',
        f'shopcart_app_restarts_total{{{metric_labels}}} {restarts}',
        '',
    ])

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/metrics':
            self.send_response(404)
            self.end_headers()
            return
        try:
            payload = collect().encode()
            self.send_response(200)
        except Exception as error:
            payload = f'# collection_error {type(error).__name__}\n'.encode()
            self.send_response(503)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        return

HTTPServer(('0.0.0.0', 9101), Handler).serve_forever()
