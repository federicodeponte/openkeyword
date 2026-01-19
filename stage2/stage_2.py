"""
Stage 2: Deep Research

Discovers hyper-niche keywords from Reddit, Quora, and forums
using Gemini with Google Search grounding.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import List

from google import genai
from google.genai import types

from .stage2_models import Stage2Input, Stage2Output, ResearchKeyword

logger = logging.getLogger(__name__)

# Response schema for research keywords
RESEARCH_KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "intent": {"type": "string", "enum": ["question", "commercial", "informational", "transactional", "comparison"]},
                    "source": {"type": "string"},
                    "url": {"type": "string"},
                    "quote": {"type": "string"},
                    "source_title": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "upvotes": {"type": "integer"},
                    "pain_point_extracted": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                },
                "required": ["keyword", "intent", "source"],
            },
        }
    },
    "required": ["keywords"],
}


async def run_stage_2(input_data: Stage2Input) -> Stage2Output:
    """
    Run Stage 2: Deep Research

    Args:
        input_data: Stage2Input with company context and config

    Returns:
        Stage2Output with discovered keywords
    """
    logger.info("=" * 60)
    logger.info("[Stage 2] Deep Research")
    logger.info("=" * 60)

    if not input_data.enable_research:
        logger.info("  Research disabled, skipping")
        return Stage2Output(keywords=[], platforms_searched=[], ai_calls=0)

    company = input_data.company_context
    logger.info(f"  Company: {company.company_name}")
    logger.info(f"  Industry: {company.industry}")

    # Initialize Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable required")

    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    client = genai.Client(api_key=api_key)

    # Run research tasks in parallel
    tasks = [
        _research_reddit(client, model_name, company, input_data.language, input_data.target_count // 2),
        _research_questions(client, model_name, company, input_data.language, input_data.target_count // 2),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect keywords
    all_keywords = []
    platforms = []
    ai_calls = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Research task failed: {result}")
        elif result:
            keywords, platform, calls = result
            all_keywords.extend(keywords)
            platforms.append(platform)
            ai_calls += calls

    # Deduplicate
    seen = set()
    unique_keywords = []
    for kw in all_keywords:
        text = kw.keyword.lower().strip()
        if text and text not in seen:
            seen.add(text)
            unique_keywords.append(kw)

    logger.info(f"  ✓ Found {len(unique_keywords)} unique keywords from research")

    return Stage2Output(
        keywords=unique_keywords,
        platforms_searched=platforms,
        ai_calls=ai_calls,
    )


async def _research_reddit(
    client,
    model_name: str,
    company,
    language: str,
    target_count: int,
) -> tuple[List[ResearchKeyword], str, int]:
    """Search Reddit for keywords."""
    services_str = ", ".join(company.services[:3]) if company.services else company.industry
    current_date = datetime.now().strftime("%B %Y")

    prompt = f"""Today's date: {current_date}

Search Reddit for discussions about: {company.industry}
Related services: {services_str}

Find {target_count} unique long-tail keywords and questions.

Search queries to use:
- site:reddit.com "{company.industry} help"
- site:reddit.com "{company.industry} recommendation"
- site:reddit.com "{company.industry} vs"
- site:reddit.com "{services_str} question"

Extract:
1. Real questions people ask
2. Problem descriptions (pain points)
3. Specific terminology used
4. Comparison phrases
5. "How to" queries

For EACH keyword, capture:
- The exact keyword/phrase
- Full URL to the Reddit thread
- Actual quote from the discussion
- Thread title
- Subreddit name
- Upvote count if visible

Return JSON with array of keywords."""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=RESEARCH_KEYWORD_SCHEMA,
            ),
        )

        data = _parse_response(response)
        keywords = [
            ResearchKeyword(
                keyword=kw.get("keyword", ""),
                intent=kw.get("intent", "question"),
                source=kw.get("source", "research_reddit"),
                url=kw.get("url"),
                quote=kw.get("quote"),
                source_title=kw.get("source_title"),
                subreddit=kw.get("subreddit"),
                upvotes=kw.get("upvotes"),
                pain_point_extracted=kw.get("pain_point_extracted"),
                sentiment=kw.get("sentiment"),
            )
            for kw in data.get("keywords", [])
            if kw.get("keyword")
        ]

        logger.info(f"    Reddit: {len(keywords)} keywords")
        return keywords, "reddit", 1

    except Exception as e:
        logger.error(f"Reddit research failed: {e}")
        return [], "reddit", 1


async def _research_questions(
    client,
    model_name: str,
    company,
    language: str,
    target_count: int,
) -> tuple[List[ResearchKeyword], str, int]:
    """Search Quora and forums for questions."""
    services_str = ", ".join(company.services[:3]) if company.services else company.industry
    current_date = datetime.now().strftime("%B %Y")

    prompt = f"""Today's date: {current_date}

Search for questions about: {company.industry}
Related services: {services_str}

Find {target_count} unique questions and long-tail keywords.

Search queries:
- site:quora.com "{company.industry}"
- "{company.industry}" people also ask
- "{services_str}" how to
- "{company.industry}" forum discussion

Extract:
1. Actual questions people ask
2. "How to" queries
3. "Best way to" phrases
4. Comparison questions
5. Specific pain points

For EACH keyword, capture:
- The exact question/keyword
- Source URL
- Source type (quora, forum, paa)

Return JSON with array of keywords."""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=RESEARCH_KEYWORD_SCHEMA,
            ),
        )

        data = _parse_response(response)
        keywords = [
            ResearchKeyword(
                keyword=kw.get("keyword", ""),
                intent=kw.get("intent", "question"),
                source=kw.get("source", "research_quora"),
                url=kw.get("url"),
                quote=kw.get("quote"),
                source_title=kw.get("source_title"),
                pain_point_extracted=kw.get("pain_point_extracted"),
                sentiment=kw.get("sentiment"),
            )
            for kw in data.get("keywords", [])
            if kw.get("keyword")
        ]

        logger.info(f"    Quora/Forums: {len(keywords)} keywords")
        return keywords, "quora", 1

    except Exception as e:
        logger.error(f"Question research failed: {e}")
        return [], "quora", 1


def _parse_response(response) -> dict:
    """Parse JSON response from Gemini."""
    if not hasattr(response, "text") or not response.text:
        return {"keywords": []}

    text = response.text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse research response: {text[:200]}")
        return {"keywords": []}
