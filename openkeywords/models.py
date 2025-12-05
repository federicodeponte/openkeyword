"""
Data models for OpenKeywords
"""

from typing import Optional
from pydantic import BaseModel, Field


class CompanyInfo(BaseModel):
    """Company information for keyword generation"""

    name: str = Field(..., description="Company name")
    url: str = Field(default="", description="Company website URL")
    industry: Optional[str] = Field(default=None, description="Industry category")
    description: Optional[str] = Field(default=None, description="Company description")
    services: list[str] = Field(default_factory=list, description="Services offered")
    products: list[str] = Field(default_factory=list, description="Products offered")
    brands: list[str] = Field(default_factory=list, description="Brand names to include")
    target_location: Optional[str] = Field(default=None, description="Target location/region")
    target_audience: Optional[str] = Field(default=None, description="Target audience")
    competitors: list[str] = Field(default_factory=list, description="Competitor URLs")


class GenerationConfig(BaseModel):
    """Configuration for keyword generation"""

    target_count: int = Field(default=50, description="Target number of keywords")
    min_score: int = Field(default=40, description="Minimum company-fit score to include")
    enable_clustering: bool = Field(default=True, description="Group keywords into clusters")
    cluster_count: int = Field(default=6, description="Target number of clusters")
    language: str = Field(default="english", description="Target language (any language)")
    region: str = Field(default="us", description="Target region/country code")
    enable_research: bool = Field(
        default=False,
        description="Enable deep research (Reddit, Quora, forums) for hyper-niche keywords"
    )
    enable_serp_analysis: bool = Field(
        default=False,
        description="Enable SERP analysis for AEO opportunity scoring (uses DataForSEO)"
    )
    serp_sample_size: int = Field(
        default=15,
        description="Number of top keywords to analyze for SERP features"
    )
    enable_volume_lookup: bool = Field(
        default=False,
        description="Get real search volumes from DataForSEO Keywords Data API"
    )


class Keyword(BaseModel):
    """A single keyword with metadata"""

    keyword: str = Field(..., description="The keyword text")
    intent: str = Field(
        default="informational",
        description="Search intent: informational, commercial, transactional, question, comparison",
    )
    score: int = Field(default=0, description="Company-fit score (0-100)")
    cluster_name: Optional[str] = Field(default=None, description="Semantic cluster name")
    is_question: bool = Field(default=False, description="Is this a question keyword?")
    volume: int = Field(default=0, description="Monthly search volume (from SE Ranking)")
    difficulty: int = Field(default=50, description="SEO difficulty score (from SE Ranking)")
    source: str = Field(
        default="ai_generated",
        description="Keyword source: ai_generated, gap_analysis, research_reddit, research_quora, research_niche"
    )
    # AEO/SERP features
    aeo_opportunity: int = Field(default=0, description="AEO opportunity score (0-100)")
    has_featured_snippet: bool = Field(default=False, description="SERP has featured snippet")
    has_paa: bool = Field(default=False, description="SERP has People Also Ask")
    serp_analyzed: bool = Field(default=False, description="Whether SERP was analyzed")


class Cluster(BaseModel):
    """A cluster of related keywords"""

    name: str = Field(..., description="Cluster name")
    keywords: list[str] = Field(default_factory=list, description="Keywords in this cluster")

    @property
    def count(self) -> int:
        return len(self.keywords)


class KeywordStatistics(BaseModel):
    """Statistics about generated keywords"""

    total: int = Field(default=0, description="Total keywords generated")
    avg_score: float = Field(default=0.0, description="Average company-fit score")
    intent_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Count by intent type"
    )
    word_length_distribution: dict[str, int] = Field(
        default_factory=dict, description="Count by word length category"
    )
    source_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Count by source (ai_generated, gap_analysis, research)"
    )
    duplicate_count: int = Field(default=0, description="Duplicates removed")


class GenerationResult(BaseModel):
    """Result of keyword generation"""

    keywords: list[Keyword] = Field(default_factory=list)
    clusters: list[Cluster] = Field(default_factory=list)
    statistics: KeywordStatistics = Field(default_factory=KeywordStatistics)
    processing_time_seconds: float = Field(default=0.0)

    def to_csv(self, filepath: str) -> None:
        """Export keywords to CSV file"""
        import csv

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["keyword", "intent", "score", "cluster", "is_question", "volume", "difficulty", "source", "aeo_opportunity", "has_featured_snippet", "has_paa"]
            )
            for kw in self.keywords:
                writer.writerow(
                    [
                        kw.keyword,
                        kw.intent,
                        kw.score,
                        kw.cluster_name or "",
                        kw.is_question,
                        kw.volume,
                        kw.difficulty,
                        kw.source,
                        kw.aeo_opportunity,
                        kw.has_featured_snippet,
                        kw.has_paa,
                    ]
                )

    def to_json(self, filepath: str) -> None:
        """Export to JSON file"""
        import json

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return self.model_dump()


