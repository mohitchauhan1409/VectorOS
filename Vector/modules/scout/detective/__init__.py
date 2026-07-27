"""Detective sub-module of SCOUT — uncovers decision-makers and their contact data (email, LinkedIn, phone)."""

from modules.scout.detective.agent import DetectiveAgent
from modules.scout.detective.pipeline import DetectivePipeline, run

__all__ = ["DetectiveAgent", "DetectivePipeline", "run"]
