"""
Floom wrapper for OpenKeyword.

Exposes the keyword research pipeline as a Floom action.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def research(
    company_url: str,
    company_name: str = "",
    target_count: int = 50,
    language: str = "en",
    region: str = "us",
) -> dict:
    """Run the keyword research pipeline for a company."""
    print(f"Starting keyword research for: {company_url}")
    print(f"Target: {target_count} keywords, language={language}, region={region}")

    from run_pipeline import run_pipeline

    results = asyncio.run(run_pipeline(
        company_url=company_url,
        company_name=company_name if company_name else None,
        target_count=int(target_count),
        language=language,
        region=region,
        enable_research=False,
        enable_clustering=True,
        min_score=40,
        cluster_count=6,
    ))

    # Build keyword table (list of dicts for Floom table output)
    keywords_table = []
    for kw in results.get("keywords", []):
        keywords_table.append({
            "keyword": kw.get("keyword", ""),
            "intent": kw.get("intent", ""),
            "score": kw.get("score", 0),
            "cluster": kw.get("cluster_name", ""),
            "source": kw.get("source", ""),
        })

    # Build markdown summary
    stats = results.get("statistics", {})
    company = results.get("company", {})
    summary = _build_summary(company, stats, results)

    print(f"Research complete: {stats.get('total_keywords', 0)} keywords in {stats.get('duration_seconds', 0)}s")

    return {
        "summary": summary,
        "keywords": keywords_table,
        "clusters": results.get("clusters", []),
        "full_results": results,
    }


def _build_summary(company: dict, stats: dict, results: dict) -> str:
    """Build markdown summary of keyword research results."""
    lines = []
    lines.append(f"# Keyword Research: {company.get('name', 'Unknown')}")
    lines.append("")
    lines.append(f"**URL:** {company.get('url', 'N/A')}")
    lines.append(f"**Industry:** {company.get('industry', 'N/A')}")
    lines.append("")

    lines.append("## Results Overview")
    lines.append(f"- **Total Keywords:** {stats.get('total_keywords', 0)}")
    lines.append(f"- **Clusters:** {stats.get('total_clusters', 0)}")
    lines.append(f"- **Average Score:** {stats.get('avg_score', 0)}")
    lines.append(f"- **AI Calls:** {stats.get('ai_calls', 0)}")
    lines.append(f"- **Duration:** {stats.get('duration_seconds', 0)}s")
    lines.append("")

    # Intent breakdown
    intent = results.get("intent_breakdown", {})
    if intent:
        lines.append("## Intent Breakdown")
        for intent_type, count in sorted(intent.items(), key=lambda x: -x[1]):
            lines.append(f"- **{intent_type}:** {count}")
        lines.append("")

    # Top clusters
    clusters = results.get("clusters", [])
    if clusters:
        lines.append("## Top Clusters")
        for c in clusters[:6]:
            name = c.get("name", "Unnamed")
            kws = c.get("keywords", [])
            lines.append(f"### {name} ({len(kws)} keywords)")
            for kw in kws[:5]:
                if isinstance(kw, str):
                    lines.append(f"- {kw}")
                else:
                    lines.append(f"- {kw}")
            if len(kws) > 5:
                lines.append(f"- *...and {len(kws) - 5} more*")
            lines.append("")

    return "\n".join(lines)
