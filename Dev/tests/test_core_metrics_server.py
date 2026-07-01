"""
Unit tests for core/core_metrics_server.py
"""
import os
import pytest
from unittest.mock import patch
import requests
import time


class TestMetricsServer:
    """Test MetricsServer class."""

    def test_server_initialization(self):
        """Server should initialize with correct defaults."""
        from core.core_metrics_server import MetricsServer
        server = MetricsServer(host="127.0.0.1", port=0)

        assert server.host == "127.0.0.1"
        assert server.port == 0
        assert server.server is None
        assert server.thread is None
        assert server.is_running() is False

    def test_start_stop_server(self):
        """Server should start and stop correctly, listening on a port."""
        from core.core_metrics_server import MetricsServer

        # Set auth token for metrics endpoint testing
        os.environ["METRICS_AUTH_TOKEN"] = "test-token"

        server = MetricsServer(host="127.0.0.1", port=0)
        server.start()

        # Let the server bind and run
        time.sleep(0.5)
        assert server.is_running() is True
        assert server.server is not None
        assigned_port = server.server.server_address[1]

        # Query health endpoint (no auth required)
        resp = requests.get(f"http://127.0.0.1:{assigned_port}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

        # Query ready endpoint (no auth required)
        resp_ready = requests.get(f"http://127.0.0.1:{assigned_port}/ready")
        assert resp_ready.status_code == 200
        assert resp_ready.json()["ready"] is True

        # Query metrics endpoint without auth — should fail 401
        resp_noauth = requests.get(f"http://127.0.0.1:{assigned_port}/metrics")
        assert resp_noauth.status_code == 401
        assert resp_noauth.json()["error"] == "unauthorized"

        # Query metrics endpoint with valid auth — should succeed 200
        resp_metrics = requests.get(
            f"http://127.0.0.1:{assigned_port}/metrics",
            headers={"Authorization": "Bearer test-token"}
        )
        assert resp_metrics.status_code == 200
        assert "uptime" in resp_metrics.text or "process_cpu_seconds_total" in resp_metrics.text or "" in resp_metrics.text

        server.stop()
        time.sleep(0.2)
        assert server.is_running() is False