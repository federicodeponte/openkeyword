"""
Deep Research Engine - Find hyper-niche keywords from real user discussions.

Uses Google Search grounding to find:
- Reddit discussions (pain points, questions, terminology)
- Quora questions (real user language)
- Forum posts (niche communities)
- People Also Ask (Google PAA)
- Blog comments and reviews

This finds keywords that AI alone would never generate.
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Response schema for structured research output
RESEARCH_KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "The exact keyword/phrase"},
                    "intent": {"type": "string", "enum": ["question", "commercial", "informational", "transactional", "comparison"]},
                    "source": {"type": "string", "description": "Platform where found (reddit, quora, forum)"},
                    "url": {"type": "string", "description": "Full URL to the discussion/thread"},
                    "quote": {"type": "string", "description": "Actual quote from the discussion"},
                    "source_title": {"type": "string", "description": "Thread/question title"},
                    "source_author": {"type": "string", "description": "Username/author"},
                    "source_date": {"type": "string", "description": "ISO date when posted"},
                    "subreddit": {"type": "string", "description": "Subreddit name (for Reddit)"},
                    "upvotes": {"type": "integer", "description": "Upvotes/likes count"},
                    "comments_count": {"type": "integer", "description": "Number of comments"},
                    "pain_point_extracted": {"type": "string", "description": "What problem they're facing"},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                },
                "required": ["keyword", "intent", "source"]
            }
        }
    },
    "required": ["keywords"]
}

# Community sources to prioritize for keyword discovery
RESEARCH_SOURCES = [
    "site:reddit.com",
    "site:quora.com",
    "people also ask",
    "forum",
    "community",
]


class ResearchEngine:
    """
    Deep research engine using Google Search grounding.

    Discovers hyper-niche, long-tail keywords and questions from:
    - Reddit (authentic user discussions)
    - Quora (real questions people ask)
    - Forums (niche communities)
    - People Also Ask (Google suggestions)

    Uses Gemini with Google Search tool for grounded research.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-pro-preview",
    ):
        """
        Initialize the research engine.

        Args:
            api_key: Google API key (or set GEMINI_API_KEY env var)
            model: Gemini model to use
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set GEMINI_API_KEY env var or pass api_key."
            )

        # Use the google-genai SDK for Google Search grounding
        try:
            from google import genai
            from google.genai import types

            self.genai = genai
            self.types = types
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = model
            self._has_search_tools = True
            logger.info(f"Research engine initialized with Google Search grounding (model: {model})")
        except ImportError:
            # Fallback to older SDK without search tools
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model)
            self._has_search_tools = False
            logger.warning(
                "google-genai SDK not available. Install with: pip install google-genai"
            )
            logger.warning("Falling back to simulated research without live search.")

    async def discover_keywords(
        self,
        company_name: str,
        industry: str,
        services: list[str],
        products: list[str] = None,
        target_location: str = "United States",
        language: str = "english",
        target_count: int = 30,
    ) -> list[dict]:
        """
        Discover hyper-niche keywords through deep research.

        Searches Reddit, Quora, forums for real user language.

        Args:
            company_name: Company name
            industry: Industry/niche
            services: List of services
            products: Optional list of products
            target_location: Target market location
            language: Target language
            target_count: Number of keywords to find

        Returns:
            List of keyword dicts with source attribution
        """
        all_keywords = []

        # Over-generate from each source to account for deduplication
        # Each source gets 50% of target, so total raw is ~150% before dedup
        per_source = max(target_count // 2, 15)

        # Research tasks in parallel
        tasks = [
            self._research_reddit(industry, services, language, per_source),
            self._research_questions(industry, services, language, per_source),
            self._research_niche_terms(
                industry, services, products or [], language, per_source
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Research task failed: {result}")
            elif result:
                all_keywords.extend(result)

        logger.info(f"Deep research found {len(all_keywords)} raw keywords")

        # Deduplicate
        seen = set()
        unique = []
        for kw in all_keywords:
            text = kw.get("keyword", "").lower().strip()
            if text and text not in seen:
                seen.add(text)
                unique.append(kw)

        logger.info(f"After dedup: {len(unique)} unique keywords from research")
        return unique

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _research_reddit(
        self,
        industry: str,
        services: list[str],
        language: str,
        target_count: int,
    ) -> list[dict]:
        """Search Reddit for real user keywords and questions."""
        services_str = ", ".join(services[:3]) if services else industry

        # Get current date
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year

        prompt = f"""Today's date: {current_date}

You are a keyword researcher. Search Reddit for REAL discussions about {industry}.

Search for: "{industry} site:reddit.com" and "{services_str} site:reddit.com"

Find {target_count} unique keywords/phrases that REAL USERS use when discussing:
- Problems they face related to {services_str}
- Questions they ask
- Solutions they're looking for
- Specific terminology and jargon
- Pain points and frustrations
- HYPER-LOCAL queries (city-specific, region-specific, language-specific)

Focus on:
- Long-tail keywords (4-7 words)
- Question-based keywords (how, what, why, can I, should I)
- Problem-based keywords (problem with, issue, help with, struggling with)
- Comparison keywords (vs, versus, alternative to, better than)
- Location-specific keywords (in [city], near me, [region] specific)
- Include current year {current_year} for time-sensitive queries

IMPORTANT: Find NICHE keywords that typical AI keyword generators would miss.
Look for the SPECIFIC language and terminology Reddit users actually use.
Include HYPER-LOCAL variations (cities, neighborhoods, regional terms).

For EACH keyword found, provide:
- The exact keyword/phrase
- Intent type
- URL to the Reddit post/thread
- Actual quote from the discussion (what the user said)
- Thread title
- Author username (if available)
- Subreddit name
- Upvotes count (if available)
- Comments count (if available)
- Date posted (if available)
- Extracted pain point (what problem they're facing)
- Sentiment (positive/negative/neutral)

Output JSON:
{{"keywords": [
  {{
    "keyword": "exact phrase from reddit",
    "intent": "question|commercial|informational|transactional|comparison",
    "source": "reddit",
    "url": "https://reddit.com/r/subreddit/comments/...",
    "quote": "actual quote from the discussion",
    "source_title": "thread title",
    "source_author": "username",
    "source_date": "2024-11-15T14:32:00Z",
    "subreddit": "r/subreddit",
    "upvotes": 247,
    "comments_count": 89,
    "pain_point_extracted": "what problem they're facing",
    "sentiment": "positive|negative|neutral",
    "context": "brief context where found"
  }}
]}}"""

        return await self._execute_grounded_research(prompt, "reddit")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _research_questions(
        self,
        industry: str,
        services: list[str],
        language: str,
        target_count: int,
    ) -> list[dict]:
        """Search Quora and People Also Ask for real questions."""
        services_str = ", ".join(services[:3]) if services else industry

        # Get current date
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year

        prompt = f"""Today's date: {current_date}

You are a keyword researcher. Search for REAL QUESTIONS people ask about {industry}.

Search: "{industry} site:quora.com" and "people also ask {services_str}"

Find {target_count} unique QUESTION keywords that real users ask about:
- {services_str}
- Problems in {industry}
- Buying decisions
- Comparisons and alternatives
- HYPER-LOCAL questions (location-specific, market-specific)

Focus on:
- Complete question phrases (how do I, what is the best, why does)
- Specific problem questions (why won't, how to fix, what to do when)
- Decision questions (should I, is it worth, which is better)
- "People Also Ask" style questions
- Location-specific questions (in [city], for [region], [language] speakers)
- Include current year {current_year} for time-sensitive questions

These should be REAL questions from Quora, forums, and Google PAA.
Find questions that typical AI generators would miss.
Include HYPER-LOCAL variations (cities, regions, languages).

For EACH question found, provide:
- The exact question
- URL to the Quora question or PAA source
- Actual answer snippet or discussion quote
- Question title
- Author name (if available)
- Views count (if available)
- Date posted (if available)
- Extracted pain point
- Sentiment

Output JSON:
{{"keywords": [
  {{
    "keyword": "exact question from research",
    "intent": "question",
    "source": "quora_paa",
    "url": "https://quora.com/...",
    "quote": "actual answer or discussion quote",
    "source_title": "question title",
    "source_author": "author name",
    "source_date": "2024-10-22T09:15:00Z",
    "views": 12400,
    "pain_point_extracted": "what problem they're asking about",
    "sentiment": "positive|negative|neutral",
    "context": "where found"
  }}
]}}"""

        return await self._execute_grounded_research(prompt, "quora_paa")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _research_niche_terms(
        self,
        industry: str,
        services: list[str],
        products: list[str],
        language: str,
        target_count: int,
    ) -> list[dict]:
        """Search for niche terminology and specific use cases."""
        context = f"{industry}, {', '.join(services[:2])}"
        if products:
            context += f", {', '.join(products[:2])}"

        prompt = f"""You are a keyword researcher. Search for NICHE terminology in {industry}.

Search forums, communities, and specialized sites for: "{context}"

Find {target_count} unique NICHE keywords including:
- Industry-specific terminology and jargon
- Specific use cases (e.g., "project management for construction companies")
- Role-specific keywords (e.g., "CRM for sales managers")
- Problem-specific keywords (e.g., "inventory management for small retail")
- Feature-specific keywords (e.g., "kanban board software")
- Location or segment specific (e.g., "accounting software for freelancers UK")

Focus on:
- Hyper-specific long-tail keywords (5-8 words)
- Keywords with modifiers (best, free, affordable, enterprise)
- Use-case specific (for startups, for agencies, for remote teams)
- Industry vertical specific

Find the EXACT terminology and phrases professionals use.

For EACH niche term found, provide:
- The exact niche keyword
- Intent type
- URL to the forum/blog post
- Actual quote or snippet
- Post title
- Author (if available)
- Forum/platform name
- Date (if available)
- Extracted use case or context
- Sentiment

Output JSON:
{{"keywords": [
  {{
    "keyword": "niche term found",
    "intent": "commercial|informational|transactional",
    "source": "niche_research",
    "url": "https://forum.com/...",
    "quote": "actual quote or snippet",
    "source_title": "post title",
    "source_author": "author",
    "source_date": "2024-12-01T16:45:00Z",
    "topic_category": "forum category",
    "pain_point_extracted": "use case or context",
    "sentiment": "positive|negative|neutral",
    "context": "context"
  }}
]}}"""

        return await self._execute_grounded_research(prompt, "niche_research")

    async def _execute_grounded_research(
        self, prompt: str, source_type: str
    ) -> list[dict]:
        """Execute a research prompt with Google Search grounding."""
        if self._has_search_tools:
            return await self._execute_with_search_tools(prompt, source_type)
        else:
            return await self._execute_simulated_research(prompt, source_type)

    async def _execute_with_search_tools(
        self, prompt: str, source_type: str
    ) -> list[dict]:
        """Execute research with Google Search grounding (new SDK)."""
        try:
            # Use Google Search tool for grounded research
            # CRITICAL: Use response_schema to enforce structured output
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=self.types.GenerateContentConfig(
                    tools=[self.types.Tool(google_search=self.types.GoogleSearch())],
                    temperature=0.5,
                    response_mime_type="application/json",
                    response_schema=RESEARCH_KEYWORD_SCHEMA,
                ),
            )

            # Parse response
            response_text = response.text
            keywords = self._parse_keywords_response(response_text)

            # Extract grounding metadata for URLs and citations
            grounding_urls = []
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    # Extract web search queries
                    queries = getattr(candidate.grounding_metadata, 'web_search_queries', [])
                    if queries:
                        logger.info(f"Search queries used: {queries[:3]}")
                    
                    # Extract grounding chunks (contains URLs and citations)
                    grounding_chunks = getattr(candidate.grounding_metadata, 'grounding_chunks', [])
                    for chunk in grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            if hasattr(chunk.web, 'uri'):
                                grounding_urls.append(chunk.web.uri)
                            elif hasattr(chunk.web, 'url'):
                                grounding_urls.append(chunk.web.url)
            
            # Enhance keywords with grounding URLs if available
            if grounding_urls and keywords:
                # Try to match URLs to keywords (simple heuristic: assign in order)
                for i, kw in enumerate(keywords):
                    if i < len(grounding_urls) and not kw.get('url'):
                        kw['url'] = grounding_urls[i]
                        logger.debug(f"Assigned grounding URL to keyword: {kw.get('keyword', '')[:50]}")

            logger.info(f"Research ({source_type}): found {len(keywords)} keywords")
            return keywords

        except Exception as e:
            logger.error(f"Search-grounded research failed: {e}")
            # Fallback to simulated research
            return await self._execute_simulated_research(prompt, source_type)

    async def _execute_simulated_research(
        self, prompt: str, source_type: str
    ) -> list[dict]:
        """Fallback: Execute research without live search (older SDK)."""
        try:
            # Modify prompt to simulate research
            fallback_prompt = prompt.replace(
                "Search for:",
                "Based on your knowledge of typical discussions, imagine what you would find if searching for:"
            ).replace(
                "Search:",
                "Based on your knowledge, generate realistic keywords as if you searched:"
            )

            # Use the new SDK for fallback too
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=fallback_prompt,
                config=self.types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )

            keywords = self._parse_keywords_response(response.text)
            logger.info(f"Simulated research ({source_type}): {len(keywords)} keywords")
            return keywords

        except Exception as e:
            logger.error(f"Simulated research failed: {e}")
            return []

    def _parse_keywords_response(self, response_text: str) -> list[dict]:
        """Parse keywords from AI response."""
        try:
            text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            keywords_data = data.get("keywords", [])

            # Validate and clean keywords
            valid_keywords = []
            for kw in keywords_data:
                keyword_text = kw.get("keyword", "").strip()
                if not keyword_text or len(keyword_text) < 5:
                    continue

                # Clean up the keyword
                keyword_text = re.sub(r'\s+', ' ', keyword_text)  # Normalize whitespace

                # Extract all enhanced fields
                keyword_dict = {
                    "keyword": keyword_text,
                    "intent": kw.get("intent", "informational"),
                    "source": kw.get("source", "research"),
                    "context": kw.get("context", ""),
                    "is_question": keyword_text.lower().startswith(
                        ("how", "what", "why", "when", "where", "which", "who", "can", "should", "is", "are", "does", "do")
                    ),
                    "score": 0,  # Will be scored later
                    # Enhanced fields
                    "url": kw.get("url", ""),
                    "quote": kw.get("quote", ""),
                    "source_title": kw.get("source_title"),
                    "source_author": kw.get("source_author"),
                    "source_date": kw.get("source_date"),
                    "upvotes": kw.get("upvotes"),
                    "comments_count": kw.get("comments_count"),
                    "views": kw.get("views"),
                    "subreddit": kw.get("subreddit"),
                    "topic_category": kw.get("topic_category"),
                    "pain_point_extracted": kw.get("pain_point_extracted"),
                    "sentiment": kw.get("sentiment"),
                    "author_karma": kw.get("author_karma"),
                    "author_verified": kw.get("author_verified"),
                    "source_authority_score": kw.get("source_authority_score"),
                }
                valid_keywords.append(keyword_dict)

            return valid_keywords

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse research response: {e}")
            return []
    
    def _aggregate_research_data(self, keywords: list[dict]) -> dict:
        """
        Aggregate research data by keyword.
        Groups sources, extracts common pain points, solutions, sentiment.
        """
        from collections import defaultdict
        
        keyword_sources = defaultdict(list)
        platforms = set()
        pain_points = defaultdict(int)
        solutions = defaultdict(int)
        sentiment_counts = defaultdict(int)
        
        for kw in keywords:
            keyword = kw.get("keyword", "")
            if not keyword:
                continue
            
            # Validate URL - must be valid HTTP(S) URL or empty
            url = kw.get("url", "")
            if url and not (url.startswith("http://") or url.startswith("https://")):
                # Invalid URL - set to empty rather than storing invalid value
                logger.debug(f"Invalid URL for keyword '{keyword}': '{url}' - setting to empty")
                url = ""
            
            # Build ResearchSource-like dict
            source_dict = {
                "keyword": keyword,
                "quote": kw.get("quote", kw.get("context", "")) or "",
                "url": url,
                "platform": self._detect_platform(url, kw.get("source", "")),
                "source_title": kw.get("source_title"),
                "source_author": kw.get("source_author"),
                "source_date": kw.get("source_date"),
                "upvotes": kw.get("upvotes"),
                "comments_count": kw.get("comments_count"),
                "views": kw.get("views"),
                "subreddit": kw.get("subreddit"),
                "topic_category": kw.get("topic_category"),
                "pain_point_extracted": kw.get("pain_point_extracted"),
                "sentiment": kw.get("sentiment"),
                "author_karma": kw.get("author_karma"),
                "author_verified": kw.get("author_verified"),
                "source_authority_score": kw.get("source_authority_score"),
            }
            
            # Only include source if it has quote or URL (minimum data requirement)
            if not source_dict["quote"] and not source_dict["url"]:
                continue  # Skip sources with no useful data
            
            keyword_sources[keyword].append(source_dict)
            platform = source_dict["platform"]
            if platform:
                platforms.add(platform)
            
            if source_dict["pain_point_extracted"]:
                pain_points[source_dict["pain_point_extracted"]] += 1
            
            sentiment = source_dict["sentiment"]
            if sentiment:
                sentiment_counts[sentiment] += 1
        
        # Build aggregated data
        aggregated = {}
        for keyword, sources in keyword_sources.items():
            # Sort by engagement (upvotes + comments)
            sources_sorted = sorted(
                sources,
                key=lambda s: (s.get("upvotes", 0) or 0) + (s.get("comments_count", 0) or 0),
                reverse=True
            )
            
            # Extract top pain points for this keyword
            keyword_pain_points = [
                s.get("pain_point_extracted") for s in sources 
                if s.get("pain_point_extracted")
            ]
            
            aggregated[keyword] = {
                "sources": sources_sorted,
                "total_sources": len(sources),
                "platforms": list(platforms),
                "pain_points": list(set(keyword_pain_points))[:5],  # Top 5 unique
                "sentiment_breakdown": dict(sentiment_counts),
            }
        
        return aggregated
    
    def _detect_platform(self, url: str, source: str) -> str:
        """Detect platform from URL or source."""
        url_lower = url.lower()
        if "reddit.com" in url_lower or source == "reddit" or source == "research_reddit":
            return "reddit"
        elif "quora.com" in url_lower or source == "quora" or source == "research_quora":
            return "quora"
        elif "indiehackers.com" in url_lower or "hackernews" in url_lower or "hn" in url_lower:
            return "forum"
        elif any(domain in url_lower for domain in ["forum", "community", "discussion"]):
            return "forum"
        else:
            return "blog" if url else source

