"""
Stage 6: SERP Analysis & Volume Lookup

Enriches keywords with search volume, difficulty, and AEO opportunity scores
using DataForSEO API.

This stage is optional - only runs when enable_serp_analysis or enable_volume_lookup
is True in the request.
"""

import asyncio
import logging
from typing import List

from clients.dataforseo_client import DataForSEOClient

from .stage6_models import Stage6Input, Stage6Output
from stage5.stage5_models import ClusteredKeyword

logger = logging.getLogger(__name__)

# Shared client instance
_dataforseo_client = None


def _get_dataforseo_client() -> DataForSEOClient:
    """Get or create shared DataForSEO client."""
    global _dataforseo_client
    if _dataforseo_client is None:
        _dataforseo_client = DataForSEOClient()
    return _dataforseo_client


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

    client = _get_dataforseo_client()

    if not client.is_configured():
        logger.warning("  DataForSEO not configured - skipping enrichment")
        return Stage6Output(keywords=input_data.keywords)

    keywords = list(input_data.keywords)
    keyword_texts = [kw.keyword for kw in keywords]

    api_calls = 0
    api_cost = 0.0
    serp_analyzed_count = 0
    volume_enriched_count = 0

    # Volume lookup for all keywords using DataForSEO Keywords Data API
    if input_data.enable_volume_lookup:
        logger.info(f"  Getting volume data for {len(keyword_texts)} keywords...")

        keyword_data = await client.get_keyword_data(
            keywords=keyword_texts,
            language=input_data.language,
            country=input_data.region,
        )

        api_calls += 1  # Single batch request
        api_cost += len(keyword_texts) * 0.000075  # ~$0.075 per 1000 keywords

        # Enrich keywords with volume and difficulty
        for kw in keywords:
            kw_lower = kw.keyword.lower()
            if kw_lower in keyword_data:
                data = keyword_data[kw_lower]
                kw.volume = data.volume
                kw.difficulty = data.difficulty
                volume_enriched_count += 1

        logger.info(f"  ✓ Got volume data for {volume_enriched_count} keywords")

    # SERP analysis for top keywords
    if input_data.enable_serp_analysis:
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
                _analyze_serp_for_keyword(client, kw, input_data.language, input_data.region)
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
                    kw.serp_analyzed = True
                    serp_analyzed_count += 1

            api_calls += len(batch)
            api_cost += len(batch) * 0.0005  # $0.50 per 1000 queries

            # Small delay between batches
            if i + batch_size < len(sample_keywords):
                await asyncio.sleep(0.5)

        logger.info(f"  ✓ SERP analyzed {serp_analyzed_count} keywords")

    logger.info(f"  API calls: {api_calls}, Est. cost: ${api_cost:.4f}")

    return Stage6Output(
        keywords=keywords,
        serp_analyzed_count=serp_analyzed_count,
        volume_enriched_count=volume_enriched_count,
        api_calls=api_calls,
        api_cost=api_cost,
    )


async def _analyze_serp_for_keyword(
    client: DataForSEOClient,
    keyword: ClusteredKeyword,
    language: str,
    region: str,
) -> dict:
    """
    Analyze SERP for a single keyword.

    Returns dict with:
    - aeo_opportunity: 0-100 score
    - has_featured_snippet: bool
    - has_paa: bool
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

    return {
        "aeo_opportunity": aeo_score,
        "has_featured_snippet": has_fs,
        "has_paa": has_paa,
    }
