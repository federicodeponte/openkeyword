# ABOUTME: SERP analysis for AEO prioritization using standalone DataForSEO client
# ABOUTME: Detects featured snippets, PAA questions, competition levels for agency-level output

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Lazy import for DataForSEO client
_dataforseo_client = None


def _get_dataforseo_client(login: Optional[str] = None, password: Optional[str] = None):
    """Lazily initialize DataForSEO client."""
    global _dataforseo_client
    if _dataforseo_client is None:
        from .dataforseo_client import DataForSEOClient
        _dataforseo_client = DataForSEOClient(login=login, password=password)
    return _dataforseo_client


@dataclass
class SerpFeatures:
    """SERP features for a keyword."""
    has_featured_snippet: bool = False
    featured_snippet_text: Optional[str] = None
    featured_snippet_url: Optional[str] = None
    
    has_paa: bool = False
    paa_questions: list[str] = field(default_factory=list)
    
    related_searches: list[str] = field(default_factory=list)
    
    # Competition indicators
    organic_results_count: int = 0
    top_domains: list[str] = field(default_factory=list)
    
    # AEO opportunity score (0-100)
    aeo_opportunity: int = 0
    aeo_reason: str = ""


@dataclass 
class SerpAnalysis:
    """Full SERP analysis result."""
    keyword: str
    features: SerpFeatures
    error: Optional[str] = None
    
    # Bonus keywords discovered from SERP
    bonus_keywords: list[str] = field(default_factory=list)


class SerpAnalyzer:
    """
    Analyze SERPs for AEO opportunities using DataForSEO.
    
    This provides agency-level SERP analysis:
    - Featured snippet detection (high AEO value)
    - PAA question extraction (bonus keywords)
    - Related search discovery
    - Competition analysis
    - AEO opportunity scoring
    
    Usage:
        analyzer = SerpAnalyzer()  # Uses DATAFORSEO_LOGIN/PASSWORD env vars
        analyses, bonus_keywords = await analyzer.analyze_keywords(["what is SEO"])
        
        for kw, analysis in analyses.items():
            print(f"{kw}: AEO Score {analysis.features.aeo_opportunity}")
    """
    
    def __init__(
        self,
        dataforseo_login: Optional[str] = None,
        dataforseo_password: Optional[str] = None,
        max_concurrent: int = 5,
        language: str = "en",
        country: str = "us",
        # Legacy parameter for backwards compatibility
        serp_endpoint: Optional[str] = None,
    ):
        """
        Initialize SERP analyzer.
        
        Args:
            dataforseo_login: DataForSEO API login (or set DATAFORSEO_LOGIN env var)
            dataforseo_password: DataForSEO API password (or set DATAFORSEO_PASSWORD env var)
            max_concurrent: Max concurrent SERP requests
            language: Language code for SERP (e.g., "en", "de")
            country: Country code for SERP (e.g., "us", "de")
            serp_endpoint: Deprecated - use dataforseo credentials instead
        """
        self.dataforseo_login = dataforseo_login or os.getenv("DATAFORSEO_LOGIN")
        self.dataforseo_password = dataforseo_password or os.getenv("DATAFORSEO_PASSWORD")
        self.max_concurrent = max_concurrent
        self.language = language
        self.country = country
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client = None
        
        # Legacy endpoint support (for backwards compatibility)
        self.serp_endpoint = serp_endpoint or os.getenv("SERP_ENDPOINT")
        
        if self.is_configured():
            logger.info(f"SERP Analyzer initialized with DataForSEO (lang={language}, country={country})")
        else:
            logger.warning(
                "SERP Analyzer: DataForSEO not configured. "
                "Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables."
            )
    
    def is_configured(self) -> bool:
        """Check if DataForSEO credentials are configured."""
        return bool(self.dataforseo_login and self.dataforseo_password)
    
    def _get_client(self):
        """Get or create DataForSEO client."""
        if self._client is None:
            from .dataforseo_client import DataForSEOClient
            self._client = DataForSEOClient(
                login=self.dataforseo_login,
                password=self.dataforseo_password,
            )
        return self._client
    
    async def analyze_keywords(
        self,
        keywords: list[str],
        extract_bonus: bool = True,
    ) -> tuple[dict[str, SerpAnalysis], list[str]]:
        """
        Analyze multiple keywords for SERP features.
        
        Args:
            keywords: List of keywords to analyze
            extract_bonus: Whether to extract bonus keywords from PAA/related
            
        Returns:
            Tuple of:
            - Dict mapping keyword -> SerpAnalysis
            - List of bonus keywords discovered from PAA/related searches
        """
        if not keywords:
            return {}, []
        
        if not self.is_configured():
            logger.warning("DataForSEO not configured - returning empty SERP analysis")
            return {kw: SerpAnalysis(keyword=kw, features=SerpFeatures(), error="DataForSEO not configured") for kw in keywords}, []
        
        logger.info(f"Analyzing SERP for {len(keywords)} keywords...")
        
        # Run analyses in parallel with semaphore limiting
        tasks = [self._analyze_single(kw) for kw in keywords]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analyses = {}
        all_bonus_keywords = set()
        
        for kw, result in zip(keywords, results):
            if isinstance(result, Exception):
                logger.error(f"SERP analysis failed for '{kw}': {result}")
                analyses[kw] = SerpAnalysis(
                    keyword=kw,
                    features=SerpFeatures(),
                    error=str(result)
                )
            else:
                analyses[kw] = result
                if extract_bonus:
                    all_bonus_keywords.update(result.bonus_keywords)
        
        # Remove original keywords from bonus
        bonus_list = [b for b in all_bonus_keywords if b.lower() not in {k.lower() for k in keywords}]
        
        logger.info(f"SERP analysis complete. Found {len(bonus_list)} bonus keywords from PAA/related")
        
        return analyses, bonus_list
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _analyze_single(self, keyword: str) -> SerpAnalysis:
        """Analyze SERP for a single keyword using DataForSEO."""
        async with self._semaphore:
            try:
                client = self._get_client()
                response = await client.search(
                    query=keyword,
                    num_results=10,
                    language=self.language,
                    country=self.country,
                )
                
                if not response.success:
                    return SerpAnalysis(
                        keyword=keyword,
                        features=SerpFeatures(),
                        error=response.error or "SERP search failed"
                    )
                
                return self._parse_serp_response(keyword, response)
                
            except Exception as e:
                logger.error(f"SERP analysis error for '{keyword}': {e}")
                return SerpAnalysis(
                    keyword=keyword,
                    features=SerpFeatures(),
                    error=str(e)
                )
    
    def _parse_serp_response(self, keyword: str, response) -> SerpAnalysis:
        """Parse DataForSEO response into analysis."""
        features = SerpFeatures()
        bonus_keywords = []
        
        # Featured snippet
        if response.featured_snippet:
            features.has_featured_snippet = True
            features.featured_snippet_text = response.featured_snippet.get("snippet", "")
            features.featured_snippet_url = response.featured_snippet.get("link", "")
        
        # People Also Ask
        if response.people_also_ask:
            features.has_paa = True
            features.paa_questions = [q.get("question", "") for q in response.people_also_ask if q.get("question")]
            # PAA questions are excellent bonus keywords
            bonus_keywords.extend(features.paa_questions)
        
        # Related searches
        if response.related_searches:
            features.related_searches = [r.get("query", "") for r in response.related_searches if r.get("query")]
            bonus_keywords.extend(features.related_searches)
        
        # Organic results analysis
        features.organic_results_count = len(response.results)
        
        # Extract top domains for competition analysis
        top_domains = []
        for r in response.results[:5]:
            link = r.link if hasattr(r, 'link') else r.get("link", "")
            if link:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(link).netloc.replace("www.", "")
                    if domain:
                        top_domains.append(domain)
                except:
                    pass
        features.top_domains = top_domains
        
        # Calculate AEO opportunity score
        features.aeo_opportunity, features.aeo_reason = self._calculate_aeo_opportunity(
            keyword, features
        )
        
        return SerpAnalysis(
            keyword=keyword,
            features=features,
            bonus_keywords=[b for b in bonus_keywords if b],
        )
    
    def _calculate_aeo_opportunity(
        self, keyword: str, features: SerpFeatures
    ) -> tuple[int, str]:
        """
        Calculate AEO opportunity score (0-100).
        
        High scores = better opportunity for AEO/featured snippets.
        """
        score = 50  # Base score
        reasons = []
        
        # Featured snippet already exists = opportunity to take it
        if features.has_featured_snippet:
            score += 25
            reasons.append("Has featured snippet (can be captured)")
        
        # PAA = Google wants Q&A content
        if features.has_paa:
            score += 15
            reasons.append("Has PAA section")
            if len(features.paa_questions) >= 4:
                score += 5
                reasons.append("Rich PAA (4+ questions)")
        
        # Question keyword = higher AEO value
        question_words = ["how", "what", "why", "when", "where", "who", "which", "can", "does", "is"]
        if any(keyword.lower().startswith(w) for w in question_words):
            score += 10
            reasons.append("Question keyword")
        
        # Competition analysis
        big_players = ["wikipedia", "amazon", "youtube", "facebook", "linkedin", "reddit", "quora"]
        big_player_count = sum(1 for d in features.top_domains if any(bp in d for bp in big_players))
        
        if big_player_count == 0:
            score += 10
            reasons.append("No major sites in top 5")
        elif big_player_count >= 3:
            score -= 15
            reasons.append("High competition (3+ major sites)")
        
        # Cap score
        score = max(0, min(100, score))
        
        reason_str = "; ".join(reasons) if reasons else "Average opportunity"
        
        return score, reason_str


async def analyze_for_aeo(
    keywords: list[str],
    language: str = "en",
    country: str = "us",
    dataforseo_login: Optional[str] = None,
    dataforseo_password: Optional[str] = None,
    # Legacy parameter
    serp_endpoint: Optional[str] = None,
) -> tuple[dict[str, SerpAnalysis], list[str]]:
    """
    Convenience function to analyze keywords for AEO opportunity.
    
    Args:
        keywords: Keywords to analyze
        language: Language code
        country: Country code  
        dataforseo_login: Optional DataForSEO login (uses env var if not provided)
        dataforseo_password: Optional DataForSEO password (uses env var if not provided)
        serp_endpoint: Deprecated - use DataForSEO credentials instead
        
    Returns:
        Tuple of (analyses dict, bonus keywords list)
    """
    analyzer = SerpAnalyzer(
        dataforseo_login=dataforseo_login,
        dataforseo_password=dataforseo_password,
        language=language,
        country=country,
    )
    return await analyzer.analyze_keywords(keywords)


# CLI for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        keywords = sys.argv[1:] if len(sys.argv) > 1 else [
            "how to optimize for AI Overviews",
            "best AEO tools 2024",
            "answer engine optimization strategy",
        ]
        
        print(f"\n🔍 Analyzing SERP for {len(keywords)} keywords...\n")
        
        analyses, bonus = await analyze_for_aeo(keywords)
        
        for kw, analysis in analyses.items():
            f = analysis.features
            print(f"━━━ {kw} ━━━")
            if analysis.error:
                print(f"  Error: {analysis.error}")
            else:
                print(f"  AEO Score: {f.aeo_opportunity}/100 - {f.aeo_reason}")
                print(f"  Featured Snippet: {'✅' if f.has_featured_snippet else '❌'}")
                print(f"  PAA Questions: {len(f.paa_questions)}")
                if f.paa_questions:
                    for q in f.paa_questions[:3]:
                        print(f"    • {q}")
                print(f"  Top Domains: {', '.join(f.top_domains[:3])}")
            print()
        
        if bonus:
            print(f"🎁 Bonus keywords from PAA/Related ({len(bonus)}):")
            for b in bonus[:10]:
                print(f"  + {b}")
    
    asyncio.run(main())
