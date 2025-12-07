# ABOUTME: SERP analysis using Gemini Google Search grounding (no DataForSEO needed!)
# ABOUTME: Detects featured snippets, PAA questions, competition levels using free Google Search

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


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
    
    # Volume estimate (using Gemini analysis)
    volume_estimate: Optional[str] = None  # "high", "medium", "low"
    volume_reasoning: Optional[str] = None


@dataclass 
class SerpAnalysis:
    """Full SERP analysis result."""
    keyword: str
    features: SerpFeatures
    error: Optional[str] = None
    
    # Bonus keywords discovered from SERP
    bonus_keywords: list[str] = field(default_factory=list)


class GeminiSerpAnalyzer:
    """
    Analyze SERPs for AEO opportunities using Gemini Google Search grounding.
    
    This provides FREE SERP analysis using Gemini's native Google Search:
    - Featured snippet detection (high AEO value)
    - PAA question extraction (bonus keywords)
    - Related search discovery
    - Competition analysis
    - AEO opportunity scoring
    - Volume estimates (no API needed!)
    
    Advantages over DataForSEO:
    - ✅ FREE (uses Gemini API you already have)
    - ✅ Real-time Google Search results
    - ✅ Natural language analysis of SERP features
    - ✅ Volume estimates based on search context
    - ✅ No separate API credentials needed
    
    Usage:
        analyzer = GeminiSerpAnalyzer(gemini_api_key="your_key")
        analyses, bonus_keywords = await analyzer.analyze_keywords(["what is SEO"])
        
        for kw, analysis in analyses.items():
            print(f"{kw}: AEO Score {analysis.features.aeo_opportunity}")
    """
    
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        max_concurrent: int = 5,
        language: str = "en",
        country: str = "us",
        model: str = "gemini-2.0-flash-exp",  # Use Flash 2.0 with grounding!
    ):
        """
        Initialize Gemini SERP analyzer.
        
        Args:
            gemini_api_key: Gemini API key (or set GEMINI_API_KEY env var)
            max_concurrent: Max concurrent SERP requests
            language: Language code for SERP (e.g., "en", "de")
            country: Country code for SERP (e.g., "us", "de")
            model: Gemini model to use (must support Google Search)
        """
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.max_concurrent = max_concurrent
        self.language = language
        self.country = country
        self.model = model
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required for Gemini SERP analysis")
        
        # Use the NEW google-genai SDK (same as ResearchEngine!)
        try:
            from google import genai
            from google.genai import types
            
            self.genai = genai
            self.types = types
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = model
            logger.info(f"Gemini SERP Analyzer initialized with Google Search (lang={language}, country={country}, model={model})")
        except ImportError:
            raise ImportError(
                "google-genai SDK required for SERP analysis with Google Search. "
                "Install with: pip install google-genai"
            )
        
        logger.info(f"Gemini SERP Analyzer initialized (lang={language}, country={country}, model={model})")
    
    def is_configured(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key)
    
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
        
        logger.info(f"Analyzing SERP for {len(keywords)} keywords using Gemini...")
        
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
        """Analyze SERP for a single keyword using Gemini Google Search."""
        async with self._semaphore:
            try:
                # Craft prompt - Gemini will use Google Search grounding
                prompt = f"""Search Google for: "{keyword}" (country: {self.country}, language: {self.language})

Analyze the search results and provide a SERP analysis in JSON format:

{{
  "has_featured_snippet": true/false,
  "featured_snippet_text": "excerpt" or null,
  "featured_snippet_url": "URL" or null,
  "has_paa": true/false,
  "paa_questions": ["question 1", "question 2"],
  "related_searches": ["related 1", "related 2"],
  "top_domains": ["domain1.com", "domain2.com"],
  "organic_results_count": 10,
  "volume_estimate": "high/medium/low",
  "volume_reasoning": "brief explanation"
}}

Extract PAA questions, related searches, and top ranking domains. 
Estimate search volume based on competition and domain authority.
Return ONLY valid JSON."""

                # Make async request using NEW SDK (same as ResearchEngine)
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                    config=self.types.GenerateContentConfig(
                        tools=[self.types.Tool(google_search=self.types.GoogleSearch())],
                        temperature=0.3,
                    ),
                )
                
                # Parse response
                response_text = response.text.strip()
                
                # Extract JSON from response (handle markdown code blocks)
                import json
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                data = json.loads(response_text)
                
                return self._parse_gemini_response(keyword, data)
                
            except Exception as e:
                logger.error(f"Gemini SERP analysis error for '{keyword}': {e}")
                return SerpAnalysis(
                    keyword=keyword,
                    features=SerpFeatures(),
                    error=str(e)
                )
    
    def _parse_gemini_response(self, keyword: str, data: dict) -> SerpAnalysis:
        """Parse Gemini response into analysis."""
        features = SerpFeatures()
        bonus_keywords = []
        
        # Featured snippet
        features.has_featured_snippet = data.get("has_featured_snippet", False)
        features.featured_snippet_text = data.get("featured_snippet_text")
        features.featured_snippet_url = data.get("featured_snippet_url")
        
        # People Also Ask
        features.has_paa = data.get("has_paa", False)
        features.paa_questions = data.get("paa_questions", [])
        if features.paa_questions:
            bonus_keywords.extend(features.paa_questions)
        
        # Related searches
        features.related_searches = data.get("related_searches", [])
        bonus_keywords.extend(features.related_searches)
        
        # Organic results
        features.organic_results_count = data.get("organic_results_count", 0)
        features.top_domains = data.get("top_domains", [])
        
        # Volume estimate (Gemini's analysis)
        features.volume_estimate = data.get("volume_estimate")
        features.volume_reasoning = data.get("volume_reasoning")
        
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
        
        # Volume estimate boost
        if features.volume_estimate == "high":
            score += 10
            reasons.append("High search volume")
        elif features.volume_estimate == "low":
            score += 5
            reasons.append("Low competition (easier to rank)")
        
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


async def analyze_for_aeo_gemini(
    keywords: list[str],
    language: str = "en",
    country: str = "us",
    gemini_api_key: Optional[str] = None,
) -> tuple[dict[str, SerpAnalysis], list[str]]:
    """
    Convenience function to analyze keywords for AEO opportunity using Gemini.
    
    Args:
        keywords: Keywords to analyze
        language: Language code
        country: Country code  
        gemini_api_key: Optional Gemini API key (uses env var if not provided)
        
    Returns:
        Tuple of (analyses dict, bonus keywords list)
    """
    analyzer = GeminiSerpAnalyzer(
        gemini_api_key=gemini_api_key,
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
        
        print(f"\n🔍 Analyzing SERP for {len(keywords)} keywords using Gemini...\n")
        
        analyses, bonus = await analyze_for_aeo_gemini(keywords)
        
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
                print(f"  Volume Estimate: {f.volume_estimate} ({f.volume_reasoning})")
                print(f"  Top Domains: {', '.join(f.top_domains[:3])}")
            print()
        
        if bonus:
            print(f"🎁 Bonus keywords from PAA/Related ({len(bonus)}):")
            for b in bonus[:10]:
                print(f"  + {b}")
    
    asyncio.run(main())

