"""
🌐 Metrics HTTP Server — Prometheus /metrics endpoint for CryptoSignal
Runs as a lightweight HTTP server alongside the main bot
"""
import json
import os
import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from core.core_metrics import get_registry, update_uptime

logger = logging.getLogger("cryptosignal.metrics-server")


def _get_auth_token() -> Optional[str]:
    """Read METRICS_AUTH_TOKEN from environment. None = no auth."""
    token = os.environ.get("METRICS_AUTH_TOKEN", "").strip()
    return token if token else None


_AUTH_TOKEN: Optional[str] = None


def _check_bearer_auth(headers) -> bool:
    global _AUTH_TOKEN
    if _AUTH_TOKEN is None:
        return True
    auth_header = headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    return auth_header[len("Bearer "):] == _AUTH_TOKEN


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""
    
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def _send_unauthorized(self):
        self._send_json(401, {"error": "unauthorized", "message": "Valid Bearer token required"})
    
    def do_GET(self):
        if self.path == "/metrics" or self.path == "/metrics/":
            auth_token = _get_auth_token()
            if auth_token is None:
                self._send_json(403, {"error": "forbidden", "message": "METRICS_AUTH_TOKEN not configured — metrics endpoint is disabled"})
                return
            # Auth is configured — validate Bearer token
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[len("Bearer "):] != auth_token:
                logger.warning(f"Unauthorized /metrics access from {self.client_address[0]}")
                self._send_unauthorized()
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()

            update_uptime()
            output = get_registry().generate_prometheus()
            self.wfile.write(output.encode("utf-8"))

        elif self.path == "/health" or self.path == "/health/":
            self._send_json(200, {
                "status": "healthy",
                "service": "YJCryptoSignal",
                "timestamp": time.time()
            })

        elif self.path == "/ready" or self.path == "/ready/":
            self._send_json(200, {
                "ready": True,
                "service": "YJCryptoSignal"
            })
        
        else:
            self._send_json(404, {"error": "not_found"})
    
    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        logger.debug(f"{self.client_address[0]} - {format % args}")


class MetricsServer:
    """HTTP server for Prometheus metrics"""
    
    def __init__(self, host: str = "0.0.0.0", port: Optional[int] = None):
        self.host = host
        self.port = port if port is not None else int(os.getenv("SCANNER_METRICS_PORT", "9090"))
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self, blocking: bool = False):
        """Start the metrics server"""
        if self._running:
            logger.warning("Metrics server already running")
            return
        
        try:
            self.server = HTTPServer((self.host, self.port), MetricsHandler)
            self._running = True
            
            if blocking:
                logger.info(f"📊 Metrics server starting on {self.host}:{self.port} (blocking)")
                self.server.serve_forever()
            else:
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()
                logger.info(f"📊 Metrics server started on {self.host}:{self.port} (background)")
        
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            self._running = False
            raise
    
    def _run(self):
        """Internal run method for background thread"""
        try:
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Metrics server error: {e}")
        finally:
            self._running = False
    
    def stop(self):
        """Stop the metrics server"""
        if self.server and self._running:
            self.server.shutdown()
            self._running = False
            logger.info("📊 Metrics server stopped")
    
    def is_running(self) -> bool:
        return self._running


# Global instance
_metrics_server: Optional[MetricsServer] = None

def start_metrics_server(host: str = "0.0.0.0", port: Optional[int] = None, blocking: bool = False) -> MetricsServer:
    global _metrics_server, _AUTH_TOKEN
    _AUTH_TOKEN = _get_auth_token()
    if _AUTH_TOKEN:
        logger.info("Metrics auth enabled (METRICS_AUTH_TOKEN set)")
    if _metrics_server is None:
        _metrics_server = MetricsServer(host, port)
    _metrics_server.start(blocking=blocking)
    return _metrics_server

def stop_metrics_server():
    """Stop the global metrics server"""
    global _metrics_server
    if _metrics_server:
        _metrics_server.stop()
        _metrics_server = None

def get_metrics_server() -> Optional[MetricsServer]:
    return _metrics_server


# ═══════════════════════════════════════════
# ASGI-compatible handler (for integration with FastAPI/Starlette)
# ═══════════════════════════════════════════

try:
    from starlette.responses import Response
    from starlette.routing import Route
    
    async def metrics_endpoint(request):
        from core.core_metrics import get_registry, update_uptime
        auth = request.headers.get("authorization", "")
        if _AUTH_TOKEN is not None and auth != f"Bearer {_AUTH_TOKEN}":
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        update_uptime()
        output = get_registry().generate_prometheus()
        return Response(content=output, media_type="text/plain; version=0.0.4; charset=utf-8")
    
    async def health_endpoint(request):
        """ASGI endpoint for /health"""
        return Response(content='{"status":"healthy","service":"YJCryptoSignal"}', media_type="application/json")
    
    METRICS_ROUTES = [
        Route("/metrics", metrics_endpoint, methods=["GET"]),
        Route("/health", health_endpoint, methods=["GET"]),
        Route("/ready", health_endpoint, methods=["GET"]),
    ]
    
except ImportError:
    # Starlette not available
    METRICS_ROUTES = []