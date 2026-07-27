"""Vector GTM Engine — entry point.

Wires the GTM modules together. Right now it just instantiates each
sub-module's agent so the structure is runnable end-to-end; real
orchestration comes later.

Modules:
  SCOUT  (Lead Generation) — radar, detective
  PULSE  (Outreach)        — inbox, connect
  CLOSER (Deal Closing)    — compass
"""

from __future__ import annotations

from modules.common.logger import get_logger
from modules.closer import CompassAgent
from modules.pulse import ConnectAgent, InboxAgent
from modules.scout import DetectiveAgent, RadarAgent

logger = get_logger("vector")


def build_engine() -> dict[str, dict[str, object]]:
    """Instantiate all GTM module agents, grouped by module."""
    return {
        "scout": {
            "radar": RadarAgent(),
            "detective": DetectiveAgent(),
        },
        "pulse": {
            "inbox": InboxAgent(),
            "connect": ConnectAgent(),
        },
        "closer": {
            "compass": CompassAgent(),
        },
    }


def main() -> None:
    logger.info("Starting Vector GTM Engine...")
    engine = build_engine()
    total = sum(len(agents) for agents in engine.values())
    for module, agents in engine.items():
        logger.info("%s → %s", module, ", ".join(agents))
    logger.info("Loaded %d modules, %d agents.", len(engine), total)


if __name__ == "__main__":
    main()
