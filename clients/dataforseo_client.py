"""
DataForSEO client for SERP analysis and keyword data.

Provides:
- SERP analysis (featured snippets, PAA, related searches)
- Search volume and CPC data
- Keyword difficulty scores

Cost: ~$0.50 per 1,000 SERP queries, ~$0.075 per 1,000 keyword lookups
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# DataForSEO location codes for common countries
LOCATION_CODES: Dict[str, int] = {
    "us": 2840,  # United States
    "uk": 2826,  # United Kingdom
    "gb": 2826,  # United Kingdom (alt)
    "ca": 2124,  # Canada
    "au": 2036,  # Australia
    "de": 2276,  # Germany
    "fr": 2250,  # France
    "es": 2724,  # Spain
    "it": 2380,  # Italy
    "jp": 2392,  # Japan
    "br": 2076,  # Brazil
    "in": 2356,  # India
    "mx": 2484,  # Mexico
    "nl": 2528,  # Netherlands
    "se": 2752,  # Sweden
    "pl": 2616,  # Poland
    "ch": 2756,  # Switzerland
    "at": 2040,  # Austria
    "be": 2056,  # Belgium
    "pt": 2620,  # Portugal
    "dk": 2208,  # Denmark
    "no": 2578,  # Norway
    "fi": 2246,  # Finland
    "ie": 2372,  # Ireland
    "nz": 2554,  # New Zealand
    "sg": 2702,  # Singapore
    "hk": 2344,  # Hong Kong
    "kr": 2410,  # South Korea
    "tw": 2158,  # Taiwan
    "ae": 2784,  # UAE
    "za": 2710,  # South Africa
    "ar": 2032,  # Argentina
    "cl": 2152,  # Chile
    "co": 2170,  # Colombia
}


@dataclass
class SearchResult:
    """Individual organic search result."""
    position: int
    title: str
    link: str
    snippet: str
    displayed_link: str = ""


@dataclass
class FeaturedSnippet:
    """Featured snippet data."""
    title: Optional[str] = None
    snippet: Optional[str] = None
    link: Optional[str] = None


@dataclass
class PeopleAlsoAsk:
    """People Also Ask item."""
    question: Optional[str] = None
    snippet: Optional[str] = None
    link: Optional[str] = None


@dataclass
class RelatedSearch:
    """Related search query."""
    query: Optional[str] = None


@dataclass
class SerpResponse:
    """SERP response from DataForSEO."""
    success: bool
    query: str
    results: List[SearchResult] = field(default_factory=list)
    provider: str = "dataforseo"
    cost: float = 0.0
    error: Optional[str] = None

    # Rich SERP features
    featured_snippet: Optional[FeaturedSnippet] = None
    people_also_ask: List[PeopleAlsoAsk] = field(default_factory=list)
    related_searches: List[RelatedSearch] = field(default_factory=list)

    # Metadata
    total_results: int = 0
    timestamp: Optional[str] = None


@dataclass
class KeywordData:
    """Keyword metrics from DataForSEO."""
    volume: int = 0
    cpc: float = 0.0
    competition: float = 0.0
    competition_level: str = ""
    difficulty: int = 50


class DataForSEOClient:
    """
    DataForSEO client for premium SERP data.

    Provides rich search results including:
    - Organic results
    - Featured snippets
    - People Also Ask
    - Related searches

    Cost: $0.50 per 1,000 queries ($0.0005 per query)
    """

    BASE_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    KEYWORD_VOLUME_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    KEYWORD_DIFFICULTY_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_difficulty/live"

    def __init__(
        self,
        login: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.api_login = login or os.environ.get("DATAFORSEO_LOGIN", "")
        self.api_password = password or os.environ.get("DATAFORSEO_PASSWORD", "")

        if self.is_configured():
            logger.info("DataForSEO client initialized")
        else:
            logger.warning(
                "DataForSEO not configured. Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD "
                "environment variables, or pass login/password to constructor."
            )

    def is_configured(self) -> bool:
        """Check if client has valid credentials."""
        return bool(self.api_login and self.api_password)

    def _get_auth_header(self) -> str:
        """Get HTTP Basic Auth header."""
        credentials = f"{self.api_login}:{self.api_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def search(
        self,
        query: str,
        num_results: int = 10,
        language: str = "en",
        country: str = "us",
    ) -> SerpResponse:
        """
        Execute search query through DataForSEO.

        Args:
            query: Search query
            num_results: Number of results (max 100)
            language: Language code
            country: Country code

        Returns:
            SerpResponse with results and SERP features
        """
        if not self.is_configured():
            return SerpResponse(
                success=False,
                query=query,
                error="DataForSEO credentials not configured.",
            )

        if not query:
            return SerpResponse(
                success=False,
                query=query,
                error="Query parameter is required",
            )

        if len(query) > 2048:
            return SerpResponse(
                success=False,
                query=query,
                error="Query too long (max 2048 characters)",
            )

        depth = min(num_results, 100)
        location_code = LOCATION_CODES.get(country.lower(), 2840)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": self._get_auth_header(),
                        "Content-Type": "application/json",
                    },
                    json=[{
                        "keyword": query,
                        "location_code": location_code,
                        "language_code": language,
                        "depth": depth,
                        "calculate_rectangles": False,
                    }],
                )

                if response.status_code in (401, 403):
                    return SerpResponse(
                        success=False,
                        query=query,
                        error="DataForSEO authentication failed.",
                    )

                if response.status_code == 400:
                    return SerpResponse(
                        success=False,
                        query=query,
                        error=f"Invalid request: {response.text[:200]}",
                    )

                response.raise_for_status()
                data = response.json()

                if not data or not data.get("tasks") or len(data["tasks"]) == 0:
                    return SerpResponse(
                        success=False,
                        query=query,
                        error="Invalid response structure from DataForSEO",
                    )

                task_result = data["tasks"][0]
                if task_result.get("status_code") != 20000:
                    error_msg = task_result.get("status_message", "Unknown error")
                    return SerpResponse(
                        success=False,
                        query=query,
                        error=f"DataForSEO task failed: {error_msg}",
                    )

                result_data = task_result.get("result", [])
                if not result_data:
                    return SerpResponse(
                        success=False,
                        query=query,
                        error="No results in DataForSEO response",
                    )

                return self._parse_response(result_data[0], query)

        except httpx.TimeoutException:
            return SerpResponse(
                success=False,
                query=query,
                error="DataForSEO request timeout after 30s",
            )
        except Exception as e:
            logger.error(f"DataForSEO error: {e}")
            return SerpResponse(
                success=False,
                query=query,
                error=f"DataForSEO error: {str(e)}",
            )

    def _parse_response(self, data: dict, query: str) -> SerpResponse:
        """Parse DataForSEO response into standardized format."""
        items = data.get("items", [])
        results: List[SearchResult] = []
        featured_snippet: Optional[FeaturedSnippet] = None
        people_also_ask: List[PeopleAlsoAsk] = []
        related_searches: List[RelatedSearch] = []

        for item in items:
            item_type = item.get("type", "")

            # Organic results
            if item_type == "organic":
                results.append(SearchResult(
                    position=item.get("rank_absolute", 0),
                    title=item.get("title", ""),
                    link=item.get("url", ""),
                    snippet=item.get("description", ""),
                    displayed_link=item.get("breadcrumb", ""),
                ))

            # Featured snippet
            elif item_type == "featured_snippet" and not featured_snippet:
                featured_snippet = FeaturedSnippet(
                    title=item.get("title"),
                    snippet=item.get("description"),
                    link=item.get("url"),
                )

            # People Also Ask
            elif item_type == "people_also_ask":
                paa_items = item.get("items", [])
                for paa in paa_items:
                    people_also_ask.append(PeopleAlsoAsk(
                        question=paa.get("title"),
                        snippet=paa.get("description"),
                        link=paa.get("url"),
                    ))

            # Related searches
            elif item_type == "related_searches":
                rs_items = item.get("items", [])
                for rs in rs_items:
                    if isinstance(rs, str):
                        related_searches.append(RelatedSearch(query=rs))
                    elif isinstance(rs, dict):
                        related_searches.append(RelatedSearch(query=rs.get("title")))

        return SerpResponse(
            success=True,
            query=query,
            results=results,
            provider="dataforseo",
            cost=0.0005,  # $0.50 per 1,000 queries
            featured_snippet=featured_snippet,
            people_also_ask=people_also_ask,
            related_searches=related_searches,
            total_results=len(results),
            timestamp=datetime.now().isoformat(),
        )

    async def get_keyword_data(
        self,
        keywords: List[str],
        language: str = "en",
        country: str = "us",
    ) -> Dict[str, KeywordData]:
        """
        Get search volume, CPC, and competition data for keywords.

        Uses DataForSEO Keywords Data API.
        Cost: ~$0.075 per 1000 keywords

        Args:
            keywords: List of keywords to lookup
            language: Language code
            country: Country code

        Returns:
            Dict mapping keyword to KeywordData
        """
        if not self.is_configured():
            logger.warning("DataForSEO not configured for keyword data")
            return {}

        if not keywords:
            return {}

        # Limit to 1000 keywords per request (API limit)
        limited_keywords = keywords[:1000]
        location_code = LOCATION_CODES.get(country.lower(), 2840)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.KEYWORD_VOLUME_URL,
                    headers={
                        "Authorization": self._get_auth_header(),
                        "Content-Type": "application/json",
                    },
                    json=[{
                        "keywords": limited_keywords,
                        "location_code": location_code,
                        "language_code": language,
                    }],
                )

                if response.status_code in (401, 403):
                    logger.error("DataForSEO authentication failed for keyword data")
                    return {}

                response.raise_for_status()
                data = response.json()

                result_map: Dict[str, KeywordData] = {}

                if data.get("tasks"):
                    for task in data["tasks"]:
                        if task.get("status_code") == 20000 and task.get("result"):
                            for item in task["result"]:
                                keyword = (item.get("keyword") or "").lower()
                                if keyword:
                                    competition = item.get("competition")
                                    # Handle competition being string or None
                                    if competition is None or isinstance(competition, str):
                                        competition = 0.0
                                    else:
                                        try:
                                            competition = float(competition)
                                        except (ValueError, TypeError):
                                            competition = 0.0

                                    comp_level = item.get("competition_level", "")
                                    difficulty_map = {"LOW": 25, "MEDIUM": 50, "HIGH": 75}
                                    difficulty = difficulty_map.get(str(comp_level).upper(), 50)

                                    result_map[keyword] = KeywordData(
                                        volume=item.get("search_volume") or 0,
                                        cpc=item.get("cpc") or 0.0,
                                        competition=competition,
                                        competition_level=str(comp_level),
                                        difficulty=difficulty,
                                    )

                logger.info(f"Got keyword data for {len(result_map)}/{len(keywords)} keywords")
                return result_map

        except httpx.TimeoutException:
            logger.error("DataForSEO keyword data request timeout")
            return {}
        except Exception as e:
            logger.error(f"DataForSEO keyword data error: {e}")
            return {}

    async def get_keyword_difficulty(
        self,
        keywords: List[str],
        language: str = "en",
        country: str = "us",
    ) -> Dict[str, int]:
        """
        Get keyword difficulty scores (0-100).

        Uses DataForSEO Keyword Difficulty API for more accurate scores.
        Cost: ~$0.05 per keyword

        Args:
            keywords: List of keywords
            language: Language code
            country: Country code

        Returns:
            Dict mapping keyword to difficulty score
        """
        if not self.is_configured():
            return {}

        if not keywords:
            return {}

        limited_keywords = keywords[:1000]
        location_code = LOCATION_CODES.get(country.lower(), 2840)

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                payload = [
                    {
                        "keyword": kw,
                        "location_code": location_code,
                        "language_code": language,
                    }
                    for kw in limited_keywords
                ]

                response = await client.post(
                    self.KEYWORD_DIFFICULTY_URL,
                    headers={
                        "Authorization": self._get_auth_header(),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code in (401, 403):
                    logger.error("DataForSEO authentication failed for keyword difficulty")
                    return {}

                response.raise_for_status()
                data = response.json()

                result_map: Dict[str, int] = {}

                if data.get("tasks"):
                    for task in data["tasks"]:
                        if task.get("status_code") == 20000 and task.get("result"):
                            for item in task["result"]:
                                keyword = (item.get("keyword") or "").lower()
                                difficulty = item.get("keyword_difficulty", 50)
                                if keyword:
                                    result_map[keyword] = int(difficulty) if difficulty else 50

                logger.info(f"Got difficulty for {len(result_map)}/{len(keywords)} keywords")
                return result_map

        except Exception as e:
            logger.error(f"DataForSEO keyword difficulty error: {e}")
            return {}


async def search_serp(
    query: str,
    country: str = "us",
    language: str = "en",
    login: Optional[str] = None,
    password: Optional[str] = None,
) -> SerpResponse:
    """Convenience function for single SERP search."""
    client = DataForSEOClient(login=login, password=password)
    return await client.search(query, country=country, language=language)
