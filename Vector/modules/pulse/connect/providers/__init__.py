"""LinkedIn transport providers.

The rest of Connect talks only to the :class:`LinkedInProvider` interface, so
the risky send layer is fully swappable:

  * ``mock``          — simulates LinkedIn; zero cost / zero ban risk (tests + dev)
  * ``phantombuster`` — real sending via PhantomBuster's cloud API

Select with ``PULSE_CONNECT_PROVIDER`` (see config). ``get_provider()`` returns
the configured instance.
"""

from __future__ import annotations

from modules.pulse.connect import config
from modules.pulse.connect.providers.base import LinkedInProvider
from modules.pulse.connect.providers.mock import MockProvider

__all__ = ["LinkedInProvider", "MockProvider", "get_provider"]

# A single shared instance per process (mock keeps in-memory sim state).
_instance: LinkedInProvider | None = None


def get_provider(name: str | None = None) -> LinkedInProvider:
    """Return the configured provider instance (cached)."""
    global _instance
    choice = (name or config.PROVIDER or "mock").lower()
    if _instance is not None and _instance.name == choice:
        return _instance
    if choice == "phantombuster":
        from modules.pulse.connect.providers.phantombuster import PhantomBusterProvider
        _instance = PhantomBusterProvider()
    elif choice == "unipile":
        from modules.pulse.connect.providers.unipile import UnipileProvider
        _instance = UnipileProvider()
    else:
        _instance = MockProvider()
    return _instance
