"""
Stage 5: Clustering

Groups keywords into semantic clusters using Gemini AI.
"""

import asyncio
import json
import logging
import os
from typing import List, Dict

from google import genai
from google.genai import types

from .stage5_models import Stage5Input, Stage5Output, ClusteredKeyword, Cluster

logger = logging.getLogger(__name__)

# Response schema for clustering
CLUSTERING_SCHEMA = {
    "type": "object",
    "properties": {
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "keywords"],
            },
        }
    },
    "required": ["clusters"],
}


async def run_stage_5(input_data: Stage5Input) -> Stage5Output:
    """
    Run Stage 5: Clustering

    Args:
        input_data: Stage5Input with scored keywords

    Returns:
        Stage5Output with clustered keywords
    """
    logger.info("=" * 60)
    logger.info("[Stage 5] Clustering")
    logger.info("=" * 60)

    company = input_data.company_context
    keywords = input_data.keywords

    logger.info(f"  Input keywords: {len(keywords)}")
    logger.info(f"  Target clusters: {input_data.cluster_count}")

    if not input_data.enable_clustering or not keywords:
        # Return keywords without clustering (preserve source attribution)
        clustered = [
            ClusteredKeyword(
                keyword=kw.keyword,
                intent=kw.intent,
                score=kw.score,
                source=kw.source,
                is_question=kw.is_question,
                cluster_name=None,
                # Source attribution
                source_url=kw.source_url,
                source_title=kw.source_title,
                source_quote=kw.source_quote,
                content_opportunity=kw.content_opportunity,
            )
            for kw in keywords
        ]
        return Stage5Output(keywords=clustered, clusters=[], ai_calls=0)

    # Initialize Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable required")

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    client = genai.Client(api_key=api_key)

    # Build clustering prompt
    keyword_list = [kw.keyword for kw in keywords]

    prompt = f"""Group these keywords into {input_data.cluster_count} semantic clusters for {company.company_name}:

INDUSTRY: {company.industry or "N/A"}

KEYWORDS:
{json.dumps(keyword_list, indent=2)}

CLUSTERING RULES:
1. Create exactly {input_data.cluster_count} clusters
2. Each cluster should have a short, descriptive name (2-4 words)
3. Group by semantic similarity and topic
4. Every keyword must belong to exactly one cluster
5. Balance cluster sizes (avoid putting everything in one cluster)

Example cluster names:
- "Pricing & Plans"
- "How-To Guides"
- "Competitor Comparisons"
- "Product Features"
- "Industry Solutions"

Return JSON with clusters array, each containing name and keywords array."""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=CLUSTERING_SCHEMA,
            ),
        )

        data = _parse_response(response)

        # Build keyword-to-cluster mapping
        keyword_cluster_map: Dict[str, str] = {}
        clusters = []

        for cluster_data in data.get("clusters", []):
            cluster_name = cluster_data.get("name", "Uncategorized")
            cluster_keywords = cluster_data.get("keywords", [])

            clusters.append(Cluster(name=cluster_name, keywords=cluster_keywords))

            for kw in cluster_keywords:
                keyword_cluster_map[kw.lower()] = cluster_name

        # Apply clusters to keywords (preserve source attribution)
        clustered_keywords = []
        for kw in keywords:
            cluster_name = keyword_cluster_map.get(kw.keyword.lower(), "Uncategorized")
            clustered_keywords.append(
                ClusteredKeyword(
                    keyword=kw.keyword,
                    intent=kw.intent,
                    score=kw.score,
                    source=kw.source,
                    is_question=kw.is_question,
                    cluster_name=cluster_name,
                    # Source attribution
                    source_url=kw.source_url,
                    source_title=kw.source_title,
                    source_quote=kw.source_quote,
                    content_opportunity=kw.content_opportunity,
                )
            )

        logger.info(f"  ✓ Created {len(clusters)} clusters")
        for cluster in clusters:
            logger.info(f"    - {cluster.name}: {cluster.count} keywords")

        return Stage5Output(
            keywords=clustered_keywords,
            clusters=clusters,
            ai_calls=1,
        )

    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        # Return keywords without clustering (preserve source attribution)
        clustered = [
            ClusteredKeyword(
                keyword=kw.keyword,
                intent=kw.intent,
                score=kw.score,
                source=kw.source,
                is_question=kw.is_question,
                cluster_name="Uncategorized",
                # Source attribution
                source_url=kw.source_url,
                source_title=kw.source_title,
                source_quote=kw.source_quote,
                content_opportunity=kw.content_opportunity,
            )
            for kw in keywords
        ]
        return Stage5Output(keywords=clustered, clusters=[], ai_calls=1)


def _parse_response(response) -> dict:
    """Parse JSON response from Gemini."""
    if not hasattr(response, "text") or not response.text:
        return {"clusters": []}

    text = response.text.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse clustering response: {text[:200]}")
        return {"clusters": []}
