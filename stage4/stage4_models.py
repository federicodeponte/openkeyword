"""
Stage 4 Models: Scoring & Deduplication

Input/Output schemas for the scoring stage.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from stage1.stage1_models import CompanyContext


class ScoredKeyword(BaseModel):
    """A scored keyword"""

    keyword: str = Field(..., description="The keyword text")
    intent: str = Field(default="informational", description="Search intent")
    score: int = Field(default=0, description="Company-fit score (0-100)")
    source: str = Field(default="ai_generated", description="Source of keyword")
    is_question: bool = Field(default=False, description="Is question keyword")
    cluster_name: Optional[str] = Field(default=None, description="Cluster name")

    # Source attribution (from Stage 2 research)
    source_url: Optional[str] = Field(default=None, description="URL to source discussion")
    source_title: Optional[str] = Field(default=None, description="Title of source thread/question")
    source_quote: Optional[str] = Field(default=None, description="Quote from source")
    content_opportunity: Optional[str] = Field(default=None, description="Content opportunity / pain point")


class Stage4Input(BaseModel):
    """Input for Stage 4: Scoring & Deduplication"""

    company_context: CompanyContext = Field(..., description="Company context")
    keywords: List[dict] = Field(..., description="All keywords from previous stages")
    min_score: int = Field(default=40, description="Minimum score to include")
    min_word_count: int = Field(default=2, description="Minimum word count")


class Stage4Output(BaseModel):
    """Output from Stage 4: Scoring & Deduplication"""

    keywords: List[ScoredKeyword] = Field(default_factory=list, description="Scored keywords")
    duplicates_removed: int = Field(default=0, description="Duplicates removed")
    low_score_removed: int = Field(default=0, description="Low score keywords removed")
    ai_calls: int = Field(default=0, description="Number of AI calls made")
