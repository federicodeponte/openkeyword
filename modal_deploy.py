"""
Modal deployment for OpenKeyword service with FREE keyword research stack
Includes: 
- Google Trends (rising queries, interest over time) - FREE
- Google Autocomplete (real user queries) - FREE  
- Gemini SERP Analysis (AEO scoring) - FREE with Gemini API key
- Deep Research (Reddit/Quora) - FREE with Gemini API key
- Semantic Clustering - FREE
"""

import modal
from pathlib import Path

app = modal.App("openkeyword")
local_dir = Path(__file__).parent

# Create image with openkeywords package installed
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi[standard]",
        "pydantic",
        "httpx",
        "google-generativeai",  # For Gemini API
        "google-genai",  # New SDK with Google Search grounding
        "aiohttp",
        "pytrends",  # Google Trends
    )
    .pip_install_from_requirements(local_dir / "requirements.txt")
    .add_local_python_source("openkeywords")
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("gemini-api-key"),  # GEMINI_API_KEY (required)
        # DataForSEO and SE Ranking are optional - only needed for paid features
    ],
    timeout=600,  # 10 minutes for full keyword generation
    memory=2048,  # 2GB for processing
)
@modal.asgi_app()
def fastapi_app():
    """FastAPI app for OpenKeyword service with FREE keyword research"""
    from fastapi import FastAPI, HTTPException, Header
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional
    import asyncio
    import os
    from openkeywords import KeywordGenerator, CompanyInfo, GenerationConfig

    app = FastAPI(
        title="OpenKeyword Service",
        description="AI-powered keyword generation with FREE research stack (Google Trends, Autocomplete, Gemini SERP)",
        version="2.0.0"
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
            "https://yourdomain.com"  # Replace with your actual domain
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Request/Response Models
    class KeywordGenerationRequest(BaseModel):
        company_name: str
        company_url: Optional[str] = None
        industry: Optional[str] = None
        services: Optional[List[str]] = None
        products: Optional[List[str]] = None
        target_audience: Optional[str] = None
        target_location: Optional[str] = None
        competitors: Optional[List[str]] = None
        target_count: int = 50
        min_score: int = 40
        language: str = "english"
        region: str = "us"
        enable_clustering: bool = True
        cluster_count: int = 6
        # FREE features (no API keys needed except Gemini)
        enable_autocomplete: bool = True  # Google Autocomplete (FREE!)
        enable_trends: bool = True  # Google Trends (FREE!)
        enable_gemini_serp: bool = True  # Gemini Google Search grounding (FREE with API key!)
        # Legacy features (require paid APIs)
        enable_research: bool = False  # Deep research (Reddit, Quora, forums)
        enable_serp_analysis: bool = False  # DataForSEO SERP feature detection
        serp_sample_size: int = 15  # How many keywords to analyze for SERP
        enable_volume_lookup: bool = False  # DataForSEO search volumes
        enable_gap_analysis: bool = False  # SE Ranking gap analysis

    class KeywordResponse(BaseModel):
        keyword: str
        intent: str
        score: int
        cluster_name: Optional[str] = None
        is_question: bool
        source: str  # ai_generated, autocomplete, trends, research_reddit, etc.
        volume: int = 0
        difficulty: int = 0
        aeo_opportunity: int = 0
        has_featured_snippet: bool = False
        has_paa: bool = False
        serp_analyzed: bool = False
        # New: Trend data
        trend_direction: Optional[str] = None  # rising, falling, stable
        trend_percentage: Optional[float] = None
        current_interest: Optional[int] = None  # Google Trends interest (0-100)

    class KeywordGenerationResponse(BaseModel):
        keywords: List[KeywordResponse]
        clusters: List[dict]
        statistics: dict
        processing_time_seconds: float

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "openkeyword",
            "version": "2.0.0",
            "features": {
                "autocomplete": "FREE - Google Autocomplete (real user queries)",
                "trends": "FREE - Google Trends (rising queries, interest over time)",
                "gemini_serp": "FREE - Gemini Google Search grounding (AEO scoring)",
                "deep_research": "Optional - Reddit/Quora/Forums",
                "serp_analysis": "Optional - DataForSEO (requires credentials)",
                "volume_lookup": "Optional - DataForSEO (requires credentials)",
                "gap_analysis": "Optional - SE Ranking (requires API key)",
            }
        }

    @app.post("/generate", response_model=KeywordGenerationResponse)
    async def generate_keywords(
        request: KeywordGenerationRequest,
        x_api_key: str = Header(None, alias="X-API-Key"),
    ):
        """
        Generate keywords with FREE OpenKeyword stack
        Accepts Gemini API key from client via X-API-Key header
        """
        try:
            # Get Gemini API key from client header or fallback to server secret
            gemini_key = x_api_key or os.environ.get("GEMINI_API_KEY")

            if not gemini_key:
                raise HTTPException(
                    status_code=400, 
                    detail="Gemini API key required. Pass via X-API-Key header or configure GEMINI_API_KEY secret."
                )

            # Optional: DataForSEO and SE Ranking (server-side only, from Modal secrets)
            dataforseo_login = os.environ.get("DATAFORSEO_LOGIN")
            dataforseo_password = os.environ.get("DATAFORSEO_PASSWORD")
            seranking_key = os.environ.get("SERANKING_API_KEY")

            generator = KeywordGenerator(
                gemini_api_key=gemini_key,
                seranking_api_key=seranking_key if seranking_key else None,
                model="gemini-3-pro-preview",  # Use Gemini 3.0 Pro Preview (best quality)
            )

            # Build company info
            company = CompanyInfo(
                name=request.company_name,
                url=request.company_url,
                industry=request.industry,
                services=request.services or [],
                products=request.products or [],
                target_audience=request.target_audience,
                target_location=request.target_location,
                competitors=request.competitors or [],
            )

            # Build generation config with FREE features enabled by default
            config = GenerationConfig(
                target_count=request.target_count,
                min_score=request.min_score,
                enable_clustering=request.enable_clustering,
                cluster_count=request.cluster_count,
                language=request.language,
                region=request.region,
                # FREE features (no API keys needed except Gemini)
                enable_autocomplete=request.enable_autocomplete,
                enable_trends=request.enable_trends,
                enable_gemini_serp=request.enable_gemini_serp,
                # Legacy features (require paid APIs)
                enable_research=request.enable_research,
                enable_serp_analysis=request.enable_serp_analysis,
                serp_sample_size=request.serp_sample_size,
                enable_volume_lookup=request.enable_volume_lookup,
            )

            # Generate keywords
            result = await generator.generate(company, config)

            # Convert to response format
            keywords_response = [
                KeywordResponse(
                    keyword=kw.keyword,
                    intent=kw.intent,
                    score=kw.score,
                    cluster_name=kw.cluster_name,
                    is_question=kw.is_question,
                    source=kw.source,
                    volume=kw.volume,
                    difficulty=kw.difficulty,
                    aeo_opportunity=getattr(kw, 'aeo_opportunity', 0),
                    has_featured_snippet=getattr(kw, 'has_featured_snippet', False),
                    has_paa=getattr(kw, 'has_paa', False),
                    serp_analyzed=getattr(kw, 'serp_analyzed', False),
                    # New: Trend data
                    trend_direction=getattr(kw, 'trend_direction', None),
                    trend_percentage=getattr(kw, 'trend_percentage', None),
                    current_interest=getattr(kw, 'current_interest', None),
                )
                for kw in result.keywords
            ]

            clusters_response = [
                {"name": cluster.name, "count": cluster.count}
                for cluster in result.clusters
            ]

            return KeywordGenerationResponse(
                keywords=keywords_response,
                clusters=clusters_response,
                statistics=result.statistics.dict(),
                processing_time_seconds=result.processing_time_seconds,  # Fixed: get from result, not statistics
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    return app

