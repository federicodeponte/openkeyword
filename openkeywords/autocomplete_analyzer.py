"""
Google Autocomplete analyzer for FREE keyword discovery.
Scrapes real user queries from Google's autocomplete suggestions.
"""
import asyncio
import logging
from typing import List, Optional, Set
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AutocompleteResult:
    """Autocomplete suggestions for a seed keyword."""
    seed_keyword: str
    suggestions: List[str] = field(default_factory=list)
    question_keywords: List[str] = field(default_factory=list)
    long_tail_keywords: List[str] = field(default_factory=list)
    error: Optional[str] = None


class GoogleAutocompleteAnalyzer:
    """
    Discover keywords using Google Autocomplete.
    
    Features:
    - Real user queries (what people actually search for)
    - Question keywords (how, what, why, etc.)
    - Long-tail keywords (3+ words)
    - Location-specific suggestions
    
    100% FREE - no API key required!
    
    Usage:
        analyzer = GoogleAutocompleteAnalyzer(country='us', language='en')
        results = await analyzer.get_suggestions('SEO')
        
        print(f"Found {len(results.suggestions)} suggestions")
        print(f"Questions: {len(results.question_keywords)}")
    """
    
    GOOGLE_AUTOCOMPLETE_URL = "http://suggestqueries.google.com/complete/search"
    
    # Question starters for question keyword generation
    QUESTION_STARTERS = [
        "how to", "what is", "why is", "when to", "when should",
        "where to", "where can", "who is", "which", "can", "does",
        "should", "will", "are", "is", "do"
    ]
    
    def __init__(
        self,
        country: str = "us",
        language: str = "en",
        max_concurrent: int = 10,
        timeout: float = 5.0,
    ):
        """
        Initialize Google Autocomplete analyzer.
        
        Args:
            country: Country code (e.g., 'us', 'uk', 'de')
            language: Language code (e.g., 'en', 'de', 'es')
            max_concurrent: Max concurrent requests
            timeout: Request timeout in seconds
        """
        self.country = country.lower()
        self.language = language.lower()
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        logger.info(f"Google Autocomplete Analyzer initialized (country={country}, language={language})")
    
    async def get_suggestions(
        self,
        keyword: str,
        include_questions: bool = True,
    ) -> AutocompleteResult:
        """
        Get autocomplete suggestions for a keyword.
        
        Args:
            keyword: Seed keyword
            include_questions: Also generate question-based suggestions
            
        Returns:
            AutocompleteResult with all suggestions
        """
        result = AutocompleteResult(seed_keyword=keyword)
        
        # Get basic suggestions
        basic_suggestions = await self._fetch_suggestions(keyword)
        result.suggestions.extend(basic_suggestions)
        
        # Get question-based suggestions
        if include_questions:
            question_suggestions = await self._fetch_question_suggestions(keyword)
            result.suggestions.extend(question_suggestions)
            result.question_keywords = question_suggestions
        
        # Remove duplicates
        result.suggestions = list(set(result.suggestions))
        
        # Identify long-tail keywords (3+ words)
        result.long_tail_keywords = [
            s for s in result.suggestions
            if len(s.split()) >= 3
        ]
        
        logger.info(f"Found {len(result.suggestions)} suggestions for '{keyword}'")
        
        return result
    
    async def get_bulk_suggestions(
        self,
        keywords: List[str],
        include_questions: bool = True,
    ) -> List[AutocompleteResult]:
        """
        Get suggestions for multiple keywords in parallel.
        
        Args:
            keywords: List of seed keywords
            include_questions: Also generate question-based suggestions
            
        Returns:
            List of AutocompleteResult objects
        """
        tasks = [
            self.get_suggestions(kw, include_questions=include_questions)
            for kw in keywords
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def _fetch_suggestions(self, keyword: str) -> List[str]:
        """Fetch basic autocomplete suggestions."""
        async with self._semaphore:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.GOOGLE_AUTOCOMPLETE_URL,
                        params={
                            'q': keyword,
                            'client': 'firefox',
                            'hl': self.language,
                            'gl': self.country,
                        }
                    )
                    response.raise_for_status()
                    
                    # Response is JSON array: [query, [suggestions], ...]
                    data = response.json()
                    suggestions = data[1] if len(data) > 1 else []
                    
                    return suggestions
            
            except Exception as e:
                logger.warning(f"Failed to fetch suggestions for '{keyword}': {e}")
                return []
    
    async def _fetch_question_suggestions(self, keyword: str) -> List[str]:
        """Fetch question-based suggestions using question starters."""
        tasks = [
            self._fetch_suggestions(f"{starter} {keyword}")
            for starter in self.QUESTION_STARTERS
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Flatten and deduplicate
        all_questions = []
        for suggestions in results:
            all_questions.extend(suggestions)
        
        return list(set(all_questions))
    
    async def discover_related_keywords(
        self,
        seed_keyword: str,
        depth: int = 2,
        max_keywords: int = 100,
    ) -> List[str]:
        """
        Discover related keywords by recursively exploring suggestions.
        
        This finds keywords you wouldn't think of!
        
        Args:
            seed_keyword: Starting keyword
            depth: How many levels deep to explore (1-3 recommended)
            max_keywords: Maximum keywords to return
            
        Returns:
            List of discovered keywords
        """
        discovered: Set[str] = set()
        to_explore = {seed_keyword}
        explored = set()
        
        for level in range(depth):
            if len(discovered) >= max_keywords:
                break
            
            # Get suggestions for all keywords at this level
            current_batch = list(to_explore - explored)
            if not current_batch:
                break
            
            logger.info(f"Level {level+1}: Exploring {len(current_batch)} keywords...")
            
            results = await self.get_bulk_suggestions(
                current_batch,
                include_questions=False  # Skip questions for speed
            )
            
            # Collect new suggestions
            next_level = set()
            for result in results:
                discovered.update(result.suggestions)
                # Use suggestions as seeds for next level
                next_level.update(result.suggestions[:5])  # Top 5 only
            
            explored.update(to_explore)
            to_explore = next_level
            
            if len(discovered) >= max_keywords:
                break
        
        logger.info(f"Discovered {len(discovered)} related keywords at depth {depth}")
        
        return list(discovered)[:max_keywords]


async def get_autocomplete_suggestions(
    keyword: str,
    country: str = "us",
    language: str = "en",
    include_questions: bool = True,
) -> AutocompleteResult:
    """
    Convenience function to get autocomplete suggestions.
    
    Args:
        keyword: Seed keyword
        country: Country code
        language: Language code
        include_questions: Include question-based suggestions
        
    Returns:
        AutocompleteResult with suggestions
    """
    analyzer = GoogleAutocompleteAnalyzer(
        country=country,
        language=language,
    )
    return await analyzer.get_suggestions(
        keyword,
        include_questions=include_questions
    )


# CLI for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        keyword = sys.argv[1] if len(sys.argv) > 1 else "SEO"
        
        print(f"\n🔍 Getting autocomplete suggestions for: {keyword}\n")
        
        analyzer = GoogleAutocompleteAnalyzer()
        result = await analyzer.get_suggestions(keyword, include_questions=True)
        
        print(f"━━━ Basic Suggestions ({len(result.suggestions)}) ━━━")
        for i, suggestion in enumerate(result.suggestions[:15], 1):
            print(f"{i:2}. {suggestion}")
        
        if result.question_keywords:
            print(f"\n━━━ Question Keywords ({len(result.question_keywords)}) ━━━")
            for i, question in enumerate(result.question_keywords[:10], 1):
                print(f"{i:2}. {question}")
        
        if result.long_tail_keywords:
            print(f"\n━━━ Long-Tail Keywords (3+ words) ({len(result.long_tail_keywords)}) ━━━")
            for i, long_tail in enumerate(result.long_tail_keywords[:10], 1):
                print(f"{i:2}. {long_tail}")
        
        # Bonus: Deep discovery
        print(f"\n━━━ Deep Discovery (depth=2) ━━━")
        discovered = await analyzer.discover_related_keywords(keyword, depth=2, max_keywords=50)
        print(f"Discovered {len(discovered)} related keywords:")
        for i, kw in enumerate(discovered[:20], 1):
            print(f"{i:2}. {kw}")
    
    asyncio.run(main())

