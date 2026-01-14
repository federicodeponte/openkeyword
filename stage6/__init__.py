"""
Stage 6: SERP Analysis & Volume Lookup

Enriches keywords with:
- Search volume from DataForSEO
- SEO difficulty scores
- AEO opportunity scores (featured snippets, PAA)
"""

from .stage_6 import run_stage_6
from .stage6_models import Stage6Input, Stage6Output

__all__ = ["run_stage_6", "Stage6Input", "Stage6Output"]
