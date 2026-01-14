"""
Stage 5 Models: Clustering

Input/Output schemas for the clustering stage.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from stage1.stage1_models import CompanyContext
from stage4.stage4_models import ScoredKeyword


class Cluster(BaseModel):
    """A cluster of related keywords"""

    name: str = Field(..., description="Cluster name")
    keywords: List[str] = Field(default_factory=list, description="Keywords in cluster")

    @property
    def count(self) -> int:
        return len(self.keywords)


class ClusteredKeyword(BaseModel):
    """A keyword with cluster assignment"""

    keyword: str = Field(..., description="The keyword text")
    intent: str = Field(default="informational", description="Search intent")
    score: int = Field(default=0, description="Company-fit score")
    source: str = Field(default="ai_generated", description="Source")
    is_question: bool = Field(default=False, description="Is question")
    cluster_name: Optional[str] = Field(default=None, description="Cluster name")

    # Source attribution (from Stage 2 research)
    source_url: Optional[str] = Field(default=None, description="URL to source discussion")
    source_title: Optional[str] = Field(default=None, description="Title of source thread/question")
    source_quote: Optional[str] = Field(default=None, description="Quote from source")
    content_opportunity: Optional[str] = Field(default=None, description="Content opportunity / pain point")

    # SERP metrics (populated by Stage 6)
    volume: int = Field(default=0, description="Monthly search volume")
    difficulty: int = Field(default=0, description="SEO difficulty 0-100")

    # AEO metrics (populated by Stage 6)
    aeo_opportunity: int = Field(default=0, description="AEO opportunity score 0-100")
    has_featured_snippet: bool = Field(default=False, description="Has featured snippet")
    has_paa: bool = Field(default=False, description="Has People Also Ask")
    serp_analyzed: bool = Field(default=False, description="SERP was analyzed")


class Stage5Input(BaseModel):
    """Input for Stage 5: Clustering"""

    company_context: CompanyContext = Field(..., description="Company context")
    keywords: List[ScoredKeyword] = Field(..., description="Scored keywords from Stage 4")
    cluster_count: int = Field(default=6, description="Target number of clusters")
    enable_clustering: bool = Field(default=True, description="Enable clustering")


class Stage5Output(BaseModel):
    """Output from Stage 5: Clustering"""

    keywords: List[ClusteredKeyword] = Field(default_factory=list, description="Clustered keywords")
    clusters: List[Cluster] = Field(default_factory=list, description="Cluster definitions")
    ai_calls: int = Field(default=0, description="Number of AI calls made")
