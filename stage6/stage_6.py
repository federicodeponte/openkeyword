"""
Stage 6: SERP Analysis & Volume Lookup

Enriches keywords with search volume, difficulty, and AEO opportunity scores.
- Serper API: Used for SERP analysis (featured snippets, PAA, AEO scoring)
- DataForSEO API: Used for volume and difficulty lookup

This stage is optional - only runs when enable_serp_analysis or enable_volume_lookup
is True in the request.
"""

import asyncio
import logging
from typing import List

from core.clients.dataforseo_client import DataForSEOClient
from core.clients.serper_client import SerperClient

from .stage6_models import Stage6Input, Stage6Output
from services.keywords.stage4.stage4_models import ScoredKeyword

logger = logging.getLogger(__name__)

# Shared client instances
_dataforseo_client = None
_serper_client = None


def _get_dataforseo_client() -> DataForSEOClient:
    """Get or create shared DataForSEO client."""
    global _dataforseo_client
    if _dataforseo_client is None:
        _dataforseo_client = DataForSEOClient()
    return _dataforseo_client


def _get_serper_client() -> SerperClient:
    """Get or create shared Serper client."""
    global _serper_client
    if _serper_client is None:
        _serper_client = SerperClient()
    return _serper_client


async def run_stage_6(input_data: Stage6Input) -> Stage6Output:
    """
    Run Stage 6: SERP Analysis & Volume Lookup

    Args:
        input_data: Stage6Input with keywords and options

    Returns:
        Stage6Output with enriched keywords
    """
    logger.info("=" * 60)
    logger.info("[Stage 6] SERP Analysis & Volume Lookup")
    logger.info("=" * 60)

    # Skip if both options are disabled
    if not input_data.enable_serp_analysis and not input_data.enable_volume_lookup:
        logger.info("  SERP analysis and volume lookup disabled, skipping")
        return Stage6Output(keywords=input_data.keywords)

    keywords = list(input_data.keywords)
    keyword_texts = [kw.keyword for kw in keywords]

    api_calls = 0
    api_cost = 0.0
    serp_analyzed_count = 0
    volume_enriched_count = 0

    # Volume and difficulty lookup using DataForSEO
    if input_data.enable_volume_lookup:
        dataforseo_client = _get_dataforseo_client()
        
        if dataforseo_client.is_configured():
            logger.info(f"  Looking up volume/difficulty for {len(keyword_texts)} keywords via DataForSEO...")
            
            keyword_data = await dataforseo_client.get_keyword_data(
                keywords=keyword_texts,
                language=input_data.language,
                country=input_data.region,
            )
            
            # Cost: ~$0.075 per 1000 keywords
            api_calls += 1
            api_cost += len(keyword_texts) * 0.000075
            
            # Enrich keywords with volume and difficulty
            for kw in keywords:
                kw_lower = kw.keyword.lower()
                if kw_lower in keyword_data:
                    data = keyword_data[kw_lower]
                    kw.volume = data.volume
                    kw.difficulty = data.difficulty
                    volume_enriched_count += 1
            
            logger.info(f"  ✓ Got volume/difficulty data for {volume_enriched_count}/{len(keyword_texts)} keywords")
        else:
            logger.warning("  DataForSEO not configured for volume/difficulty lookup - skipping")

    # SERP analysis for top keywords using Serper
    if input_data.enable_serp_analysis:
        serper_client = _get_serper_client()
        
        if not serper_client.is_configured():
            logger.warning("  Serper not configured for SERP analysis - skipping")
        else:
            # Sort by score and take top N for SERP analysis
            sorted_keywords = sorted(keywords, key=lambda k: k.score, reverse=True)
            sample_keywords = sorted_keywords[:input_data.serp_sample_size]

            logger.info(f"  Analyzing SERP for top {len(sample_keywords)} keywords...")

            # Run SERP analysis in batches to avoid rate limits
            batch_size = 5
            for i in range(0, len(sample_keywords), batch_size):
                batch = sample_keywords[i:i + batch_size]

                # Analyze batch in parallel
                tasks = [
                    _analyze_serp_for_keyword(serper_client, kw, input_data.language, input_data.region)
                    for kw in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for kw, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"  SERP analysis failed for '{kw.keyword}': {result}")
                    elif result:
                        # Update keyword with SERP data
                        kw.aeo_opportunity = result["aeo_opportunity"]
                        kw.has_featured_snippet = result["has_featured_snippet"]
                        kw.has_paa = result["has_paa"]
                        kw.serp_data = result.get("serp_data")
                        kw.serp_analyzed = True
                        serp_analyzed_count += 1

                api_calls += len(batch)
                api_cost += len(batch) * 0.0005  # $0.50 per 1000 queries

                # Small delay between batches
                if i + batch_size < len(sample_keywords):
                    await asyncio.sleep(0.5)

            logger.info(f"  ✓ SERP analyzed {serp_analyzed_count} keywords")

    logger.info(f"  API calls: {api_calls}, Est. cost: ${api_cost:.4f}")

    # Fill in estimated values for keywords that didn't get API data
    _fill_estimated_values(keywords)

    # Use model_construct to avoid Pydantic creating copies of the keywords
    # This preserves the serp_data modifications we made
    return Stage6Output.model_construct(
        keywords=keywords,
        serp_analyzed_count=serp_analyzed_count,
        volume_enriched_count=volume_enriched_count,
        api_calls=api_calls,
        api_cost=api_cost,
    )


def _fill_estimated_values(keywords: List[ScoredKeyword]) -> None:
    """
    Fill in estimated values for keywords that didn't receive API data.
    Ensures all keywords have reasonable values for display.
    """
    for kw in keywords:
        # Estimate volume if not set (0 means no data)
        if kw.volume == 0:
            kw.volume = _estimate_volume(kw)
        
        # Estimate difficulty if not set (0 means no data)
        if kw.difficulty == 0:
            kw.difficulty = _estimate_difficulty(kw)
        
        # Estimate AEO opportunity if not analyzed via SERP
        if not kw.serp_analyzed:
            kw.aeo_opportunity = _estimate_aeo_opportunity(kw)


def _estimate_volume(kw: ScoredKeyword) -> int:
    """
    Estimate search volume based on keyword characteristics.
    Returns a conservative estimate since we don't have actual data.
    Long-tail keywords typically have lower volume.
    """
    word_count = len(kw.keyword.split())
    
    # Base volume decreases with word count (long-tail = lower volume)
    if word_count <= 2:
        base_volume = 500
    elif word_count == 3:
        base_volume = 200
    elif word_count == 4:
        base_volume = 100
    elif word_count == 5:
        base_volume = 50
    else:
        base_volume = 20
    
    # Question keywords often have moderate search volume
    if kw.is_question:
        base_volume = max(base_volume, 100)
    
    # Transactional keywords often have higher volume
    if kw.intent == "transactional":
        base_volume = int(base_volume * 1.5)
    
    return base_volume


def _estimate_difficulty(kw: ScoredKeyword) -> int:
    """
    Estimate keyword difficulty based on keyword characteristics.
    Returns a value between 20-80 based on heuristics.
    """
    difficulty = 40  # Base difficulty
    
    word_count = len(kw.keyword.split())
    
    # Longer keywords (long-tail) are typically easier to rank
    if word_count >= 5:
        difficulty -= 15
    elif word_count >= 4:
        difficulty -= 10
    elif word_count >= 3:
        difficulty -= 5
    elif word_count <= 2:
        difficulty += 15  # Short keywords are more competitive
    
    # Question keywords often have less competition
    if kw.is_question:
        difficulty -= 10
    
    # Transactional keywords tend to be more competitive
    if kw.intent == "transactional":
        difficulty += 10
    elif kw.intent == "commercial":
        difficulty += 5
    
    # Clamp to valid range
    return max(20, min(80, difficulty))


def _estimate_aeo_opportunity(kw: ScoredKeyword) -> int:
    """
    Estimate AEO (AI Engine Optimization) opportunity based on keyword characteristics.
    Returns a value between 10-60 based on heuristics.
    """
    aeo_score = 25  # Base score
    
    # Question keywords have higher AEO potential
    if kw.is_question:
        aeo_score += 20
    
    # Informational intent keywords work well for AI answers
    if kw.intent == "informational":
        aeo_score += 15
    elif kw.intent == "question":
        aeo_score += 20
    
    # Longer keywords often have more specific answers
    word_count = len(kw.keyword.split())
    if word_count >= 4:
        aeo_score += 10
    elif word_count >= 3:
        aeo_score += 5
    
    # High-scoring keywords (good company fit) may have better targeting
    if kw.score >= 80:
        aeo_score += 5
    
    # Clamp to valid range (lower max since these are estimates)
    return max(10, min(60, aeo_score))


async def _analyze_serp_for_keyword(
    client: SerperClient,
    keyword: ScoredKeyword,
    language: str,
    region: str,
) -> dict:
    """
    Analyze SERP for a single keyword.

    Returns dict with:
    - aeo_opportunity: 0-100 score
    - has_featured_snippet: bool
    - has_paa: bool
    - serp_data: full SERP data for frontend display
    """
    serp = await client.search(
        query=keyword.keyword,
        language=language,
        country=region,
        num_results=10,
    )

    if not serp.success:
        return None

    # Calculate AEO opportunity score
    # Higher score = better opportunity for AI visibility
    aeo_score = 0

    has_fs = serp.featured_snippet is not None
    has_paa = len(serp.people_also_ask) > 0

    # Featured snippet present = high AEO opportunity
    if has_fs:
        aeo_score += 40

    # PAA present = content can appear in AI answers
    if has_paa:
        aeo_score += 30

    # Related searches = topic has depth
    if len(serp.related_searches) > 3:
        aeo_score += 15

    # Question keywords have higher AEO potential
    if keyword.is_question:
        aeo_score += 15

    # Cap at 100
    aeo_score = min(aeo_score, 100)

    # Build serp_data for frontend display
    # Note: serp.results contains SearchResult dataclass objects from Serper
    serp_data = {
        "organic_results": [
            {
                "position": r.position,
                "title": r.title or "",
                "url": r.link or "",
                "snippet": r.snippet or "",
            }
            for r in serp.results[:10]
        ],
        "paa_questions": [
            {
                "question": paa.question or "",
                "snippet": paa.snippet or "",
                "url": paa.link or "",
            }
            for paa in serp.people_also_ask
        ],
        "related_searches": [rs.query or "" for rs in serp.related_searches],
    }
    
    # Add featured snippet if present
    if serp.featured_snippet:
        serp_data["featured_snippet"] = {
            "type": "paragraph",
            "content": serp.featured_snippet.snippet or "",
            "source_url": serp.featured_snippet.link or "",
            "source_title": serp.featured_snippet.title or "",
        }

    return {
        "aeo_opportunity": aeo_score,
        "has_featured_snippet": has_fs,
        "has_paa": has_paa,
        "serp_data": serp_data,
    }
