"""
Stage 3: AI Keyword Generation

Generates keywords using Gemini AI based on company context.
"""

import asyncio
import json
import logging
import os
from typing import List

from google import genai
from google.genai import types

from .stage3_models import Stage3Input, Stage3Output, GeneratedKeyword

logger = logging.getLogger(__name__)

# Response schema for keyword generation
KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "intent": {"type": "string", "enum": ["transactional", "commercial", "informational", "question", "comparison"]},
                    "is_question": {"type": "boolean"},
                },
                "required": ["keyword", "intent"],
            },
        }
    },
    "required": ["keywords"],
}


async def run_stage_3(input_data: Stage3Input) -> Stage3Output:
    """
    Run Stage 3: AI Keyword Generation

    Args:
        input_data: Stage3Input with company context and research keywords

    Returns:
        Stage3Output with generated keywords
    """
    logger.info("=" * 60)
    logger.info("[Stage 3] AI Keyword Generation")
    logger.info("=" * 60)

    company = input_data.company_context
    logger.info(f"  Company: {company.company_name}")
    logger.info(f"  Research keywords: {len(input_data.research_keywords)}")

    # Initialize Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable required")

    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    client = genai.Client(api_key=api_key)

    # Calculate how many AI keywords we need
    existing_count = len(input_data.research_keywords)
    ai_target = max(input_data.target_count - existing_count, input_data.target_count // 3)

    logger.info(f"  Generating {ai_target} AI keywords")

    # Build comprehensive prompt
    products = ", ".join(company.products[:5]) if company.products else "N/A"
    services = ", ".join(company.services[:5]) if company.services else "N/A"
    pain_points = ", ".join(company.pain_points[:5]) if company.pain_points else "N/A"
    differentiators = ", ".join(company.differentiators[:3]) if company.differentiators else "N/A"

    prompt = f"""Generate {ai_target} SEO keywords for this company:

COMPANY: {company.company_name}
INDUSTRY: {company.industry or "N/A"}
PRODUCTS: {products}
SERVICES: {services}
PAIN POINTS: {pain_points}
DIFFERENTIATORS: {differentiators}
TARGET REGION: {input_data.region.upper()}
LANGUAGE: {input_data.language}

REQUIREMENTS:
1. Generate DIVERSE keywords across these intents:
   - transactional (buy, pricing, demo)
   - commercial (comparison, alternatives, vs)
   - informational (how to, what is, guide)
   - question (actual questions users ask)

2. Include:
   - Long-tail keywords (3-5 words)
   - Question keywords ("how to...", "what is...")
   - Comparison keywords ("X vs Y", "alternatives to")
   - Product-specific keywords
   - Problem-solving keywords

3. AVOID:
   - Generic industry terms
   - Single-word keywords
   - Duplicate variations

Return JSON with array of keywords, each with:
- keyword: the keyword text
- intent: one of [transactional, commercial, informational, question, comparison]
- is_question: true if it's a question"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
                response_schema=KEYWORD_SCHEMA,
            ),
        )

        data = _parse_response(response)
        keywords = [
            GeneratedKeyword(
                keyword=kw.get("keyword", ""),
                intent=kw.get("intent", "informational"),
                source="ai_generated",
                is_question=kw.get("is_question", False),
            )
            for kw in data.get("keywords", [])
            if kw.get("keyword")
        ]

        logger.info(f"  ✓ Generated {len(keywords)} AI keywords")

        return Stage3Output(
            keywords=keywords,
            ai_calls=1,
        )

    except Exception as e:
        logger.error(f"AI keyword generation failed: {e}")
        return Stage3Output(keywords=[], ai_calls=1)


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
        logger.error(f"Failed to parse keyword response: {text[:200]}")
        return {"keywords": []}
