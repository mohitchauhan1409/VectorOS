"""Convenience launcher for the Vector backend API.

    python run_api.py            # serves on http://localhost:8787
    VECTOR_API_PORT=9000 python run_api.py

Creates the SQLite schema and seeds the demo workspace on first boot.
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("VECTOR_API_PORT", "8787"))
    reload = os.getenv("VECTOR_API_RELOAD", "0") == "1"
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=reload)
