"""NewsRadar — discovers leads from news headlines.

Public entry point:

    from modules.scout.radar.NewsRadar import NewsRadarPipeline, run
    leads = run()
"""

from modules.scout.radar.NewsRadar.pipeline import NewsRadarPipeline, run

__all__ = ["NewsRadarPipeline", "run"]
