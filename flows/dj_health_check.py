"""Prefect Cloud flow that pings the dj-music REST API health endpoint.

Deploy from GitHub:

    uvx prefect-cloud deploy flows/dj_health_check.py:health_check \
        --from evgenygurin/dj-music-plugin \
        --name dj-music-health

Schedule hourly:

    uvx prefect-cloud schedule health_check/dj-music-health "0 * * * *"

Run once on demand:

    uvx prefect-cloud run health_check/dj-music-health
"""

from __future__ import annotations

import os

import httpx
from prefect import flow, get_run_logger, task

DEFAULT_URL = os.environ.get("DJ_MUSIC_API_URL", "http://127.0.0.1:8000")


@task(retries=2, retry_delay_seconds=5)
def fetch_health(base_url: str) -> dict[str, object]:
    """GET /api/health on the dj-music REST API."""
    response = httpx.get(f"{base_url}/api/health", timeout=10.0)
    response.raise_for_status()
    return response.json()


@flow(name="health_check", log_prints=True)
def health_check(base_url: str = DEFAULT_URL) -> dict[str, object]:
    """Smoke-test the dj-music REST API and surface MCP readiness.

    Returns the parsed `/api/health` payload so the Prefect run page shows
    the tool count and `mcp_ready` flag for the run.
    """
    logger = get_run_logger()
    logger.info("Pinging dj-music API at %s", base_url)
    payload = fetch_health(base_url)
    logger.info(
        "API responded: status=%s tools=%s mcp_ready=%s",
        payload.get("status"),
        payload.get("tools_discovered"),
        payload.get("mcp_ready"),
    )
    return payload


if __name__ == "__main__":
    health_check()
