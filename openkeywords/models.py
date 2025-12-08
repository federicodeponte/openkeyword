"""
Data models for OpenKeywords
"""

from typing import Optional
from datetime import datetime
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
    
    # Rich context from company analysis (optional)
    pain_points: list[str] = Field(default_factory=list, description="Customer pain points and frustrations")
    customer_problems: list[str] = Field(default_factory=list, description="Problems the solution addresses")
    use_cases: list[str] = Field(default_factory=list, description="Real scenarios where product is used")
    value_propositions: list[str] = Field(default_factory=list, description="Key value propositions")
    differentiators: list[str] = Field(default_factory=list, description="What makes them unique vs competitors")
    key_features: list[str] = Field(default_factory=list, description="Technical capabilities and features")
    solution_keywords: list[str] = Field(default_factory=list, description="Terms describing their approach")
    brand_voice: Optional[str] = Field(default=None, description="Brand communication style")


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
    research_focus: bool = Field(
        default=False,
        description="Agency mode: 70% research keywords, strict filtering of broad terms"
    )
    min_word_count: int = Field(
        default=2,
        description="Minimum word count for keywords (use 4+ for hyper-niche)"
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
    # Enhanced data capture flags
    enable_enhanced_capture: bool = Field(
        default=True,
        description="Enable enhanced data capture (URLs, quotes, citations, content briefs)"
    )
    enable_content_briefs: bool = Field(
        default=True,
        description="Generate content briefings for keywords"
    )
    enable_citations: bool = Field(
        default=True,
        description="Generate citations in APA/MLA/Chicago formats"
    )
    content_brief_count: int = Field(
        default=20,
        description="Number of top keywords to generate content briefs for"
    )
    research_sources_per_keyword: int = Field(
        default=5,
        description="Maximum research sources to capture per keyword"
    )


# ========== ENHANCED DATA CAPTURE MODELS ==========

class ResearchSource(BaseModel):
    """A single research source with full citation data."""
    
    # Core data
    keyword: str = Field(..., description="The keyword this source relates to")
    quote: str = Field(default="", description="The actual quote/snippet from discussion")
    url: str = Field(default="", description="Direct link to discussion")
    platform: str = Field(default="blog", description="Platform: reddit, quora, forum, blog")
    
    def model_post_init(self, __context):
        """Validate URL format after initialization."""
        if self.url and not (self.url.startswith("http://") or self.url.startswith("https://")):
            # Invalid URL - clear it
            self.url = ""
    
    # Citation metadata
    source_title: Optional[str] = Field(default=None, description="Thread/question title")
    source_author: Optional[str] = Field(default=None, description="Username/author")
    source_date: Optional[str] = Field(default=None, description="When posted (ISO format)")
    
    # Engagement metrics
    upvotes: Optional[int] = Field(default=None, description="Reddit upvotes")
    comments_count: Optional[int] = Field(default=None, description="Number of comments")
    views: Optional[int] = Field(default=None, description="Number of views")
    
    # Context
    subreddit: Optional[str] = Field(default=None, description="For Reddit: subreddit name")
    topic_category: Optional[str] = Field(default=None, description="For forums: topic category")
    pain_point_extracted: Optional[str] = Field(default=None, description="Extracted pain point")
    sentiment: Optional[str] = Field(default=None, description="positive, negative, or neutral")
    
    # Credibility
    author_karma: Optional[int] = Field(default=None, description="Reddit karma")
    author_verified: Optional[bool] = Field(default=None, description="Is author verified")
    source_authority_score: Optional[int] = Field(default=None, description="Source authority score (0-100)")


class ResearchData(BaseModel):
    """All research data for a keyword."""
    
    keyword: str = Field(..., description="The keyword")
    sources: list[ResearchSource] = Field(default_factory=list, description="Research sources")
    
    # Aggregated insights
    total_sources_found: int = Field(default=0, description="Total sources found")
    platforms_searched: list[str] = Field(default_factory=list, description="Platforms searched")
    most_mentioned_pain_points: list[str] = Field(default_factory=list, description="Common pain points")
    common_solutions_mentioned: list[str] = Field(default_factory=list, description="Common solutions mentioned")
    sentiment_breakdown: dict[str, int] = Field(default_factory=dict, description="Sentiment breakdown")


class ContentBrief(BaseModel):
    """Content briefing for a keyword."""
    
    content_angle: Optional[str] = Field(default=None, description="Suggested approach/angle")
    target_questions: list[str] = Field(default_factory=list, description="Questions to answer")
    content_gap: Optional[str] = Field(default=None, description="What's missing in current SERP")
    audience_pain_point: Optional[str] = Field(default=None, description="Users were looking for X")
    recommended_word_count: Optional[int] = Field(default=None, description="Recommended word count")
    fs_opportunity_type: Optional[str] = Field(default=None, description="Featured snippet opportunity type")
    research_context: Optional[str] = Field(default=None, description="Summary of user needs from research")


class SERPRanking(BaseModel):
    """A single SERP result with full data."""
    
    position: int = Field(..., description="Position 1-10")
    url: str = Field(..., description="Result URL (resolved, not redirect)")
    title: str = Field(..., description="Page title")
    description: Optional[str] = Field(default=None, description="Meta description")
    
    # Domain data
    domain: str = Field(..., description="Domain name")
    domain_authority: Optional[int] = Field(default=None, description="Domain authority score")
    is_big_brand: bool = Field(default=False, description="Is this a big brand")
    
    # Content insights
    page_type: Optional[str] = Field(default=None, description="listicle, comparison, how-to, guide, product_page")
    estimated_word_count: Optional[int] = Field(default=None, description="Estimated word count")
    publish_date: Optional[str] = Field(default=None, description="Publish date")
    last_updated: Optional[str] = Field(default=None, description="Last updated date")
    
    # SERP features
    has_featured_snippet: bool = Field(default=False, description="Has featured snippet")
    has_site_links: bool = Field(default=False, description="Has site links")
    has_reviews_stars: bool = Field(default=False, description="Has review stars")
    
    # Traffic estimate
    estimated_monthly_traffic: Optional[int] = Field(default=None, description="Estimated monthly traffic")
    
    # Meta tags (Open Graph, Twitter Cards, etc.)
    meta_tags: Optional[dict] = Field(default=None, description="Extracted meta tags (og:title, og:description, etc.)")


class FeaturedSnippetData(BaseModel):
    """Featured snippet with full citation data."""
    
    type: str = Field(..., description="paragraph, list, table, video")
    content: str = Field(..., description="The actual snippet text")
    source_url: str = Field(..., description="Source URL")
    source_domain: str = Field(..., description="Source domain")
    source_title: Optional[str] = Field(default=None, description="Source page title")
    
    # For lists/tables
    items: Optional[list[str]] = Field(default=None, description="List items")
    table_data: Optional[dict] = Field(default=None, description="Table structure")


class PAAQuestion(BaseModel):
    """People Also Ask question with source."""
    
    question: str = Field(..., description="The question")
    answer_snippet: Optional[str] = Field(default=None, description="The answer shown in PAA")
    source_url: str = Field(..., description="Source URL")
    source_domain: str = Field(..., description="Source domain")
    source_title: Optional[str] = Field(default=None, description="Source page title")


class CompleteSERPData(BaseModel):
    """Complete SERP analysis for a keyword."""
    
    keyword: str = Field(..., description="The keyword")
    search_date: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Search date (ISO timestamp)")
    country: str = Field(..., description="Country code")
    language: str = Field(..., description="Language code")
    
    # Top 10 rankings
    organic_results: list[SERPRanking] = Field(default_factory=list, description="Top 10 organic results")
    
    # SERP features
    featured_snippet: Optional[FeaturedSnippetData] = Field(default=None, description="Featured snippet")
    paa_questions: list[PAAQuestion] = Field(default_factory=list, description="People Also Ask questions")
    related_searches: list[str] = Field(default_factory=list, description="Related searches")
    
    # Images/Videos
    image_pack_present: bool = Field(default=False, description="Image pack present")
    video_results: list[dict] = Field(default_factory=list, description="Video results")
    
    # Ads
    ads_count: int = Field(default=0, description="Number of ads")
    ads_top_domains: list[str] = Field(default_factory=list, description="Top ad domains")
    
    # Aggregated insights
    avg_word_count: int = Field(default=0, description="Average word count")
    common_content_types: list[str] = Field(default_factory=list, description="Common content types")
    big_brands_count: int = Field(default=0, description="Number of big brands in top 10")
    avg_domain_authority: float = Field(default=0.0, description="Average domain authority")
    
    # Ensure None values are converted to defaults
    def __init__(self, **data):
        if "avg_domain_authority" in data and data["avg_domain_authority"] is None:
            data["avg_domain_authority"] = 0.0
        if "avg_word_count" in data and data["avg_word_count"] is None:
            data["avg_word_count"] = 0
        if "big_brands_count" in data and data["big_brands_count"] is None:
            data["big_brands_count"] = 0
        super().__init__(**data)
    
    # Opportunity analysis
    weakest_position: Optional[int] = Field(default=None, description="Lowest DA position in top 10")
    content_gaps_identified: list[str] = Field(default_factory=list, description="Content gaps")
    differentiation_opportunities: list[str] = Field(default_factory=list, description="Differentiation opportunities")


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
    
    # ========== ENHANCED DATA CAPTURE (Optional) ==========
    # Full nested data
    research_data: Optional[ResearchData] = Field(default=None, description="Full research data with sources")
    content_brief: Optional[ContentBrief] = Field(default=None, description="Content briefing")
    serp_data: Optional[CompleteSERPData] = Field(default=None, description="Complete SERP data")
    
    # Quick access fields (for CSV export)
    research_summary: Optional[str] = Field(default=None, description="Top 3 research quotes summary")
    research_source_urls: list[str] = Field(default_factory=list, description="All research source URLs")
    top_ranking_urls: list[str] = Field(default_factory=list, description="Top 10 ranking URLs")
    featured_snippet_url: Optional[str] = Field(default=None, description="Featured snippet source URL")
    paa_questions_with_urls: list[dict] = Field(default_factory=list, description="PAA questions with URLs")
    
    # Citations
    citations: list[dict] = Field(default_factory=list, description="Ready-to-use citations")


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
            # Base columns
            headers = [
                "keyword", "intent", "score", "cluster", "is_question", "volume", "difficulty", 
                "source", "aeo_opportunity", "has_featured_snippet", "has_paa"
            ]
            # Enhanced data columns
            enhanced_headers = [
                "research_summary", "research_urls", "content_angle", "target_questions", 
                "content_gap", "audience_pain_point", "top_ranking_urls", "featured_snippet_url", 
                "paa_urls", "citation_count"
            ]
            writer.writerow(headers + enhanced_headers)
            
            for kw in self.keywords:
                # Base row
                row = [
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
                # Enhanced data row (flattened)
                enhanced_row = [
                    kw.research_summary or "",
                    " | ".join(kw.research_source_urls) if kw.research_source_urls else "",
                    kw.content_brief.content_angle if kw.content_brief else "",
                    ", ".join(kw.content_brief.target_questions) if kw.content_brief and kw.content_brief.target_questions else "",
                    kw.content_brief.content_gap if kw.content_brief else "",
                    kw.content_brief.audience_pain_point if kw.content_brief else "",
                    " | ".join(kw.top_ranking_urls) if kw.top_ranking_urls else "",
                    kw.featured_snippet_url or "",
                    " | ".join([f"{q.get('question', '')} ({q.get('url', '')})" for q in kw.paa_questions_with_urls]) if kw.paa_questions_with_urls else "",
                    len(kw.citations) if kw.citations else 0,
                ]
                writer.writerow(row + enhanced_row)

    def to_json(self, filepath: str) -> None:
        """Export to JSON file"""
        import json

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return self.model_dump()

    def export_citations(self, filepath: str) -> None:
        """Export citations to separate file (Markdown format)"""
        citations_by_keyword = {}
        for kw in self.keywords:
            if kw.citations:
                citations_by_keyword[kw.keyword] = kw.citations
        
        if not citations_by_keyword:
            return
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Citations Reference\n\n")
            f.write("This file contains all citations for generated keywords.\n\n")
            
            citation_id = 1
            for keyword, citations in citations_by_keyword.items():
                f.write(f"## Keyword: {keyword}\n\n")
                for citation in citations:
                    f.write(f"**Citation #{citation_id}**\n\n")
                    f.write(f"**Type:** {citation.get('type', 'unknown')}\n")
                    if citation.get('platform'):
                        f.write(f"**Platform:** {citation.get('platform')}\n")
                    if citation.get('source'):
                        f.write(f"**Source:** {citation.get('source')}\n")
                    if citation.get('author'):
                        f.write(f"**Author:** {citation.get('author')}\n")
                    if citation.get('date'):
                        f.write(f"**Date:** {citation.get('date')}\n")
                    if citation.get('url'):
                        f.write(f"**URL:** {citation.get('url')}\n")
                    if citation.get('text'):
                        f.write(f"**Text:** {citation.get('text')}\n")
                    f.write("\n**Citations:**\n")
                    if citation.get('format_apa'):
                        f.write(f"- APA: {citation.get('format_apa')}\n")
                    if citation.get('format_mla'):
                        f.write(f"- MLA: {citation.get('format_mla')}\n")
                    if citation.get('format_chicago'):
                        f.write(f"- Chicago: {citation.get('format_chicago')}\n")
                    f.write("\n")
                    citation_id += 1
            
            f.write(f"\n**Total Citations:** {citation_id - 1}\n")


