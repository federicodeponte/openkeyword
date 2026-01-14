#!/usr/bin/env python3
"""
OpenKeywords Pipeline Orchestrator

Runs the 6-stage keyword generation pipeline:
- Stage 1: Company Analysis (runs once)
- Stage 2: Deep Research (Reddit, Quora, forums)
- Stage 3: AI Keyword Generation
- Stage 4: Scoring & Deduplication
- Stage 5: Clustering
- Stage 6: SERP Analysis & Volume Lookup (optional)

Usage:
    python run_pipeline.py --url https://example.com --count 50
    python run_pipeline.py --url https://example.com --research --count 100
    python run_pipeline.py --url https://example.com --serp-analysis --volume-lookup

Architecture:
    Stage 1: Company Analysis
         ↓
    Stage 2: Deep Research (optional)
         ↓
    Stage 3: AI Keyword Generation
         ↓
    Stage 4: Scoring & Deduplication
         ↓
    Stage 5: Clustering
         ↓
    Stage 6: SERP Analysis & Volume Lookup (optional)
         ↓
    [Output: Keywords + Clusters + SERP Data]
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load .env from current directory
load_dotenv(Path(__file__).parent / ".env")

# Add base path for imports
_BASE_PATH = Path(__file__).parent
if str(_BASE_PATH) not in sys.path:
    sys.path.insert(0, str(_BASE_PATH))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_pipeline(
    company_url: str,
    company_name: Optional[str] = None,
    target_count: int = 50,
    language: str = "en",
    region: str = "us",
    enable_research: bool = False,
    enable_clustering: bool = True,
    min_score: int = 40,
    min_word_count: int = 2,
    cluster_count: int = 6,
    enable_serp_analysis: bool = False,
    enable_volume_lookup: bool = False,
    serp_sample_size: int = 15,
) -> dict:
    """
    Run the full keyword generation pipeline.

    Args:
        company_url: Company website URL
        company_name: Optional company name override
        target_count: Target number of keywords
        language: Target language code
        region: Target region code
        enable_research: Enable deep research (Reddit, Quora)
        enable_clustering: Enable keyword clustering
        min_score: Minimum company-fit score
        min_word_count: Minimum keyword word count
        cluster_count: Number of clusters to create
        enable_serp_analysis: Enable SERP analysis for AEO opportunity scoring
        enable_volume_lookup: Get real search volumes from DataForSEO
        serp_sample_size: Number of top keywords to analyze for SERP features

    Returns:
        Dict with pipeline results
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("OpenKeywords Pipeline")
    logger.info("=" * 60)
    logger.info(f"URL: {company_url}")
    logger.info(f"Target: {target_count} keywords")
    logger.info(f"Language: {language}, Region: {region}")
    logger.info(f"Research: {'ON' if enable_research else 'OFF'}")
    logger.info(f"SERP Analysis: {'ON' if enable_serp_analysis else 'OFF'}")
    logger.info(f"Volume Lookup: {'ON' if enable_volume_lookup else 'OFF'}")
    logger.info("=" * 60)

    total_ai_calls = 0
    total_api_calls = 0
    total_api_cost = 0.0

    # =========================================================================
    # Stage 1: Company Analysis
    # =========================================================================
    from stage1 import run_stage_1
    from stage1.stage1_models import Stage1Input

    stage1_input = Stage1Input(
        company_url=company_url,
        company_name=company_name,
        language=language,
        region=region,
    )

    stage1_output = await run_stage_1(stage1_input)
    total_ai_calls += stage1_output.ai_calls

    logger.info(f"\n[Stage 1 Complete] {stage1_output.company_context.company_name}")

    # =========================================================================
    # Stage 2: Deep Research (optional)
    # =========================================================================
    from stage2 import run_stage_2
    from stage2.stage2_models import Stage2Input

    stage2_input = Stage2Input(
        company_context=stage1_output.company_context,
        language=language,
        region=region,
        target_count=target_count // 2,
        enable_research=enable_research,
    )

    stage2_output = await run_stage_2(stage2_input)
    total_ai_calls += stage2_output.ai_calls

    logger.info(f"\n[Stage 2 Complete] {len(stage2_output.keywords)} research keywords")

    # =========================================================================
    # Stage 3: AI Keyword Generation
    # =========================================================================
    from stage3 import run_stage_3
    from stage3.stage3_models import Stage3Input

    stage3_input = Stage3Input(
        company_context=stage1_output.company_context,
        research_keywords=stage2_output.keywords,
        language=language,
        region=region,
        target_count=target_count,
        enable_autocomplete=False,
    )

    stage3_output = await run_stage_3(stage3_input)
    total_ai_calls += stage3_output.ai_calls

    logger.info(f"\n[Stage 3 Complete] {len(stage3_output.keywords)} AI keywords")

    # =========================================================================
    # Combine all keywords for scoring
    # =========================================================================
    all_keywords = []

    # Add research keywords (preserve source attribution from Stage 2)
    for kw in stage2_output.keywords:
        all_keywords.append({
            "keyword": kw.keyword,
            "intent": kw.intent,
            "source": kw.source,
            "is_question": kw.intent == "question",
            # Source attribution
            "source_url": kw.url,
            "source_title": kw.source_title,
            "source_quote": kw.quote,
            "content_opportunity": kw.pain_point_extracted,
        })

    # Add AI keywords
    for kw in stage3_output.keywords:
        all_keywords.append({
            "keyword": kw.keyword,
            "intent": kw.intent,
            "source": kw.source,
            "is_question": kw.is_question,
        })

    logger.info(f"\n[Combined] {len(all_keywords)} total keywords before scoring")

    # =========================================================================
    # Stage 4: Scoring & Deduplication
    # =========================================================================
    from stage4 import run_stage_4
    from stage4.stage4_models import Stage4Input

    stage4_input = Stage4Input(
        company_context=stage1_output.company_context,
        keywords=all_keywords,
        min_score=min_score,
        min_word_count=min_word_count,
    )

    stage4_output = await run_stage_4(stage4_input)
    total_ai_calls += stage4_output.ai_calls

    logger.info(f"\n[Stage 4 Complete] {len(stage4_output.keywords)} scored keywords")

    # =========================================================================
    # Stage 5: Clustering
    # =========================================================================
    from stage5 import run_stage_5
    from stage5.stage5_models import Stage5Input

    stage5_input = Stage5Input(
        company_context=stage1_output.company_context,
        keywords=stage4_output.keywords,
        cluster_count=cluster_count,
        enable_clustering=enable_clustering,
    )

    stage5_output = await run_stage_5(stage5_input)
    total_ai_calls += stage5_output.ai_calls

    logger.info(f"\n[Stage 5 Complete] {len(stage5_output.clusters)} clusters")

    # =========================================================================
    # Stage 6: SERP Analysis & Volume Lookup (optional)
    # =========================================================================
    if enable_serp_analysis or enable_volume_lookup:
        from stage6 import run_stage_6
        from stage6.stage6_models import Stage6Input

        stage6_input = Stage6Input(
            keywords=stage5_output.keywords,
            enable_serp_analysis=enable_serp_analysis,
            enable_volume_lookup=enable_volume_lookup,
            serp_sample_size=serp_sample_size,
            language=language,
            region=region,
        )

        stage6_output = await run_stage_6(stage6_input)
        total_api_calls = stage6_output.api_calls
        total_api_cost = stage6_output.api_cost

        # Update keywords with enriched data
        stage5_output.keywords = stage6_output.keywords

        logger.info(f"\n[Stage 6 Complete] SERP: {stage6_output.serp_analyzed_count}, Volume: {stage6_output.volume_enriched_count}")

    # =========================================================================
    # Build Results
    # =========================================================================
    end_time = time.time()
    duration = end_time - start_time

    # Build statistics
    intent_breakdown = {}
    source_breakdown = {}
    total_score = 0

    for kw in stage5_output.keywords:
        intent_breakdown[kw.intent] = intent_breakdown.get(kw.intent, 0) + 1
        source_breakdown[kw.source] = source_breakdown.get(kw.source, 0) + 1
        total_score += kw.score

    avg_score = total_score / len(stage5_output.keywords) if stage5_output.keywords else 0

    results = {
        "company": {
            "name": stage1_output.company_context.company_name,
            "url": company_url,
            "industry": stage1_output.company_context.industry,
        },
        "config": {
            "language": language,
            "region": region,
            "target_count": target_count,
            "enable_research": enable_research,
            "enable_clustering": enable_clustering,
            "min_score": min_score,
        },
        "statistics": {
            "total_keywords": len(stage5_output.keywords),
            "total_clusters": len(stage5_output.clusters),
            "avg_score": round(avg_score, 1),
            "duplicates_removed": stage4_output.duplicates_removed,
            "low_score_removed": stage4_output.low_score_removed,
            "ai_calls": total_ai_calls,
            "api_calls": total_api_calls,
            "api_cost_usd": round(total_api_cost, 4),
            "duration_seconds": round(duration, 1),
        },
        "intent_breakdown": intent_breakdown,
        "source_breakdown": source_breakdown,
        "keywords": [kw.model_dump() for kw in stage5_output.keywords],
        "clusters": [c.model_dump() for c in stage5_output.clusters],
        "created_at": datetime.now().isoformat(),
    }

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Pipeline Complete")
    logger.info("=" * 60)
    logger.info(f"Keywords: {len(stage5_output.keywords)}")
    logger.info(f"Clusters: {len(stage5_output.clusters)}")
    logger.info(f"Avg Score: {avg_score:.1f}")
    logger.info(f"Duration: {duration:.1f}s")
    logger.info(f"AI Calls: {total_ai_calls}")
    logger.info("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="OpenKeywords - AI Keyword Generation Pipeline"
    )
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Company website URL",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Company name override",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Target keyword count (default: 50)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Target language (default: en)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us",
        help="Target region (default: us)",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help="Enable deep research (Reddit, Quora)",
    )
    parser.add_argument(
        "--no-clustering",
        action="store_true",
        help="Disable clustering",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=40,
        help="Minimum score (default: 40)",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=6,
        help="Number of clusters (default: 6)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--serp-analysis",
        action="store_true",
        help="Enable SERP analysis (AEO opportunity scores)",
    )
    parser.add_argument(
        "--volume-lookup",
        action="store_true",
        help="Enable volume lookup from DataForSEO",
    )
    parser.add_argument(
        "--serp-sample",
        type=int,
        default=15,
        help="Number of keywords for SERP analysis (default: 15)",
    )

    args = parser.parse_args()

    # Run pipeline
    results = asyncio.run(run_pipeline(
        company_url=args.url,
        company_name=args.name,
        target_count=args.count,
        language=args.language,
        region=args.region,
        enable_research=args.research,
        enable_clustering=not args.no_clustering,
        min_score=args.min_score,
        cluster_count=args.clusters,
        enable_serp_analysis=args.serp_analysis,
        enable_volume_lookup=args.volume_lookup,
        serp_sample_size=args.serp_sample,
    ))

    # Save output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"\nOutput saved to: {output_path}")
    else:
        # Print summary to stdout
        print(json.dumps({
            "company": results["company"]["name"],
            "keywords": results["statistics"]["total_keywords"],
            "clusters": results["statistics"]["total_clusters"],
            "avg_score": results["statistics"]["avg_score"],
            "duration": results["statistics"]["duration_seconds"],
        }, indent=2))


if __name__ == "__main__":
    main()
