"""Shared logging setup for the Vector GTM Engine."""

from __future__ import annotations

import logging

from modules.common.config import get_settings

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger with a consistent format.

    Args:
        name: Logger name, typically the module's ``__name__``.
    """
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=get_settings().log_level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
