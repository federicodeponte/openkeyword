"""
OpenKeywords - AI-powered SEO keyword generation using Gemini + SE Ranking + Deep Research + SERP Analysis.

Generate high-quality, clustered SEO keywords for any business with AEO opportunity scoring.

Features:
- AI keyword generation (Gemini)
- SE Ranking gap analysis (competitor keywords)
- Deep Research (Reddit, Quora, forums) for hyper-niche keywords
- SERP Analysis (DataForSEO) for AEO opportunity scoring

Usage:
    from openkeywords import KeywordGenerator, CompanyInfo, GenerationConfig

    generator = KeywordGenerator()
    result = await generator.generate(
        CompanyInfo(name="Acme Software", industry="B2B SaaS"),
        GenerationConfig(
            enable_research=True,       # Reddit, Quora, forums
            enable_serp_analysis=True,  # Featured snippet detection
        ),
    )

    for kw in result.keywords:
        print(f"{kw.keyword} | AEO: {kw.aeo_opportunity} | FS: {kw.has_featured_snippet}")
"""

from .models import (
    Cluster,
    CompanyInfo,
    GenerationConfig,
    GenerationResult,
    Keyword,
    KeywordStatistics,
)
from .generator import KeywordGenerator
from .seranking_client import SEORankingAPIClient
from .gap_analyzer import SEORankingAPI, AEOContentGapAnalyzer
from .researcher import ResearchEngine
from .serp_analyzer import SerpAnalyzer, SerpFeatures, SerpAnalysis, analyze_for_aeo
from .dataforseo_client import DataForSEOClient, SerpResponse, search_serp

__version__ = "0.3.0"
__all__ = [
    # Main API
    "KeywordGenerator",
    "CompanyInfo",
    "GenerationConfig",
    "GenerationResult",
    "Keyword",
    "Cluster",
    "KeywordStatistics",
    # SE Ranking
    "SEORankingAPIClient",
    "SEORankingAPI",
    "AEOContentGapAnalyzer",
    # Deep Research
    "ResearchEngine",
    # SERP Analysis (DataForSEO)
    "SerpAnalyzer",
    "SerpFeatures",
    "SerpAnalysis",
    "analyze_for_aeo",
    "DataForSEOClient",
    "SerpResponse",
    "search_serp",
]
