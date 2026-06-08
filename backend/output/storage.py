"""Storage backend — GCS in production, local filesystem in development.

Windows-compatible: uses tempfile.gettempdir() instead of hardcoded /tmp.
All paths use pathlib.Path for cross-platform compatibility.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import structlog

log = structlog.get_logger()

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "sentinel-reports")

# Cross-platform storage path:
# - Honour LOCAL_STORAGE_PATH env var if set
# - Otherwise use system temp dir (works on Windows, macOS, Linux)
_default_local_path = Path(tempfile.gettempdir()) / "sentinel-reports"
LOCAL_STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", str(_default_local_path)))


async def upload_json(run_id: str, content: bytes) -> str:
    if STORAGE_BACKEND == "gcs":
        return await _gcs_upload(run_id, content, "application/json", f"{run_id}.json")
    return await _local_upload(run_id, content, f"{run_id}.json", "json")


async def upload_pdf(run_id: str, content: bytes) -> str:
    if STORAGE_BACKEND == "gcs":
        return await _gcs_upload(run_id, content, "application/pdf", f"{run_id}.pdf")
    return await _local_upload(run_id, content, f"{run_id}.pdf", "pdf")


async def _local_upload(run_id: str, content: bytes, filename: str, ext: str) -> str:
    LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    path = LOCAL_STORAGE_PATH / filename
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, path.write_bytes, content)
    log.info("storage.local_saved", path=str(path), size=len(content))
    return f"/api/v1/reports/{run_id}/{ext}"


async def _gcs_upload(run_id: str, content: bytes, content_type: str, blob_name: str) -> str:
    try:
        from google.cloud import storage as gcs
        loop = asyncio.get_event_loop()

        def _do_upload():
            client = gcs.Client()
            bucket = client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(f"reports/{blob_name}")
            blob.upload_from_string(content, content_type=content_type)
            blob.make_public()
            return blob.public_url

        url = await loop.run_in_executor(None, _do_upload)
        log.info("storage.gcs_uploaded", blob=blob_name, url=url)
        return url
    except Exception as exc:
        log.error("storage.gcs_failed", error=str(exc))
        ext = blob_name.split(".")[-1]
        return await _local_upload(run_id, content, blob_name, ext)


def get_local_pdf_path(run_id: str) -> Path:
    """Return the local path to a stored PDF report."""
    return LOCAL_STORAGE_PATH / f"{run_id}.pdf"


def get_local_json_path(run_id: str) -> Path:
    """Return the local path to a stored JSON report."""
    return LOCAL_STORAGE_PATH / f"{run_id}.json"
