"""Thin backend-facing shim over the engine's single control panel.

All the real switches live in modules/common/control.py. This module just
re-exposes the few the backend/orchestrator need, so call sites stay stable.
The master safety switch is `VECTOR_PULSE_LIVE` (default off = SAFE).
"""

from __future__ import annotations

from modules.common import control


def is_live() -> bool:
    return control.PULSE_LIVE


def email_dry_run() -> bool:
    """Email has no mock transport — dry-run is the safe path (no SMTP/IMAP)."""
    return control.EMAIL_DRY_RUN


def connect_dry_run() -> bool:
    """LinkedIn uses the MOCK provider in safe mode (dry_run=False so it can
    simulate send + auto-accept + replies). Live mode also sends via provider."""
    return False


def mode_label() -> str:
    return control.mode_label()


def apply_safe_env() -> None:
    """No-op kept for call-site compatibility.

    Provider selection is now decided inside control.py based on PULSE_LIVE
    (mock is forced whenever the engine isn't live), so there's nothing to set.
    """
    return None
