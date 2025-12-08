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
    
    # Enhanced data capture: full SERP data
    serp_data_full: Optional[dict] = None


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

Analyze the COMPLETE SERP and provide detailed analysis in JSON format:

1. All top 10 organic results with:
   - position (1-10)
   - url (full URL)
   - title (page title)
   - description (meta description)
   - domain (domain name)
   - estimated word count
   - page type (listicle, comparison, how-to, guide, product_page, etc.)
   - publish date (if available)
   - last updated (if available)

2. Featured snippet (if present):
   - type (paragraph, list, table, video)
   - content (snippet text)
   - source_url (URL)
   - source_domain (domain)

3. People Also Ask questions (if present):
   - question (the question)
   - answer_snippet (answer shown)
   - source_url (URL)
   - source_domain (domain)

4. Related searches

5. Aggregated insights:
   - avg_word_count (average word count of top 10)
   - common_content_types (most common page types)
   - big_brands_count (number of big brands in top 10)
   - avg_domain_authority (estimated average DA)
   - content_gaps_identified (what's missing)
   - differentiation_opportunities (how to stand out)

Return JSON:
{{
  "organic_results": [
    {{"position": 1, "url": "https://...", "title": "...", "description": "...", "domain": "...", "estimated_word_count": 3200, "page_type": "comparison", "publish_date": "2024-01-15", "last_updated": "2024-11-20"}},
    ...
  ],
  "featured_snippet": {{"type": "paragraph", "content": "...", "source_url": "https://...", "source_domain": "..."}} or null,
  "paa_questions": [{{"question": "...", "answer_snippet": "...", "source_url": "https://...", "source_domain": "..."}}, ...],
  "related_searches": ["...", ...],
  "avg_word_count": 2640,
  "common_content_types": ["comparison", "listicle"],
  "big_brands_count": 6,
  "avg_domain_authority": 82.3,
  "content_gaps_identified": ["...", ...],
  "differentiation_opportunities": ["...", ...],
  "has_featured_snippet": true/false,
  "has_paa": true/false,
  "organic_results_count": 10,
  "top_domains": ["domain1.com", "domain2.com"],
  "volume_estimate": "high/medium/low",
  "volume_reasoning": "brief explanation"
}}

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
                
                # Extract real URLs from grounding metadata BEFORE parsing JSON
                real_urls_map = {}
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                        grounding_chunks = getattr(candidate.grounding_metadata, 'grounding_chunks', [])
                        for chunk in grounding_chunks:
                            try:
                                if hasattr(chunk, 'web') and chunk.web:
                                    redirect_url = None
                                    if hasattr(chunk.web, 'uri'):
                                        redirect_url = chunk.web.uri
                                    elif hasattr(chunk.web, 'url'):
                                        redirect_url = chunk.web.url
                                    
                                    if redirect_url and redirect_url.startswith("https://vertexaisearch.cloud.google.com/"):
                                        # Try to get real URL from chunk metadata if available
                                        # Sometimes the real URL is in chunk.web.title or other fields
                                        if hasattr(chunk.web, 'title'):
                                            # The title might contain hints about the real domain
                                            pass
                                        # Store redirect URL for later resolution
                                        real_urls_map[redirect_url] = redirect_url  # Will be resolved later
                            except Exception as e:
                                logger.debug(f"Error extracting grounding URL: {e}")
                
                # Parse response
                if not hasattr(response, 'text') or not response.text:
                    raise ValueError("Empty response from Gemini")
                
                response_text = response.text.strip()
                
                # Extract JSON from response (handle markdown code blocks)
                import json
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                if not response_text:
                    raise ValueError("No JSON found in response")
                
                data = json.loads(response_text)
                
                # Store redirect URLs map for later resolution
                data["_redirect_urls_map"] = real_urls_map
                
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
        
        # Store full SERP data for enhanced capture
        # Ensure we always have a dict structure even if Gemini returns minimal data
        serp_data_full = data.copy() if isinstance(data, dict) else {}
        
        # Ensure required fields exist for enhanced capture
        if "organic_results" not in serp_data_full:
            serp_data_full["organic_results"] = []
        if "paa_questions" not in serp_data_full:
            serp_data_full["paa_questions"] = []
        if "related_searches" not in serp_data_full:
            serp_data_full["related_searches"] = []
        
        return SerpAnalysis(
            keyword=keyword,
            features=features,
            bonus_keywords=[b for b in bonus_keywords if b],
            serp_data_full=serp_data_full,
        )
    
    async def _build_complete_serp_data(
        self, serp_data_full: dict, keyword: str, country: str = "us", language: str = "en"
    ) -> dict:
        """
        Build CompleteSERPData object from full SERP data.
        Resolves redirect URLs and extracts meta tags.
        
        Args:
            keyword: The keyword
            serp_data_full: Full SERP data from Gemini
            country: Country code
            language: Language code
            
        Returns:
            CompleteSERPData dict
        """
        from datetime import datetime
        from .url_extractor import resolve_urls_batch
        
        # Validate input
        if not serp_data_full or not isinstance(serp_data_full, dict):
            logger.warning(f"Invalid serp_data_full for '{keyword}': {type(serp_data_full)}")
            serp_data_full = {}
        
        # Ensure required fields exist
        if "organic_results" not in serp_data_full:
            serp_data_full["organic_results"] = []
        if "paa_questions" not in serp_data_full:
            serp_data_full["paa_questions"] = []
        if "related_searches" not in serp_data_full:
            serp_data_full["related_searches"] = []
        
        # Collect all URLs that need resolution
        urls_to_resolve = []
        
        for result in serp_data_full.get("organic_results", []):
            if not isinstance(result, dict):
                continue
            url = result.get("url", "")
            if url and url.startswith("https://vertexaisearch.cloud.google.com/"):
                urls_to_resolve.append(url)
        
        # Also check featured snippet and PAA URLs
        featured_snippet = serp_data_full.get("featured_snippet")
        if featured_snippet and isinstance(featured_snippet, dict):
            fs_url = featured_snippet.get("source_url", "")
            if fs_url and fs_url.startswith("https://vertexaisearch.cloud.google.com/"):
                urls_to_resolve.append(fs_url)
        
        for paa in serp_data_full.get("paa_questions", []):
            if not isinstance(paa, dict):
                continue
            url = paa.get("source_url", "")
            if url and url.startswith("https://vertexaisearch.cloud.google.com/"):
                urls_to_resolve.append(url)
        
        # Resolve redirects and extract meta tags in parallel
        resolved_urls = {}
        if urls_to_resolve:
            logger.info(f"Resolving {len(urls_to_resolve)} redirect URLs and extracting meta tags for '{keyword}'...")
            resolved_urls = await resolve_urls_batch(urls_to_resolve, extract_meta=True)
        
        organic_results = []
        for result in serp_data_full.get("organic_results", []):
            if not isinstance(result, dict):
                continue
            
            original_url = result.get("url", "")
            resolved_data = resolved_urls.get(original_url, {})
            if not isinstance(resolved_data, dict):
                resolved_data = {}
            resolved_url = resolved_data.get("resolved_url", original_url)
            meta_tags = resolved_data.get("meta_tags", {})
            if not isinstance(meta_tags, dict):
                meta_tags = {}
            
            # Extract domain from resolved URL
            from urllib.parse import urlparse
            try:
                parsed = urlparse(resolved_url)
                domain = parsed.netloc.replace("www.", "")
            except:
                domain = result.get("domain", "")
            
            organic_results.append({
                "position": result.get("position", 0),
                "url": resolved_url,  # Use resolved URL, not redirect
                "title": result.get("title", ""),
                "description": result.get("description"),
                "domain": domain,
                "domain_authority": result.get("domain_authority"),
                "is_big_brand": self._is_big_brand(domain),
                "page_type": result.get("page_type"),
                "estimated_word_count": result.get("estimated_word_count"),
                "publish_date": result.get("publish_date"),
                "last_updated": result.get("last_updated"),
                "has_featured_snippet": False,
                "has_site_links": False,
                "has_reviews_stars": False,
                "estimated_monthly_traffic": result.get("estimated_monthly_traffic"),
                "meta_tags": meta_tags if meta_tags else None,  # Include meta tags
            })
        
        # Resolve featured snippet URL if it's a redirect
        featured_snippet = None
        featured_snippet_raw = serp_data_full.get("featured_snippet")
        if featured_snippet_raw and isinstance(featured_snippet_raw, dict):
            fs = featured_snippet_raw
            fs_url = fs.get("source_url", "")
            if fs_url and fs_url.startswith("https://vertexaisearch.cloud.google.com/"):
                resolved_fs_data = resolved_urls.get(fs_url, {})
                if isinstance(resolved_fs_data, dict):
                    fs_url = resolved_fs_data.get("resolved_url", fs_url)
            
            featured_snippet = {
                "type": fs.get("type", "paragraph"),
                "content": fs.get("content", ""),
                "source_url": fs_url,  # Use resolved URL
                "source_domain": fs.get("source_domain", ""),
                "source_title": fs.get("source_title"),
                "items": fs.get("items"),
                "table_data": fs.get("table_data"),
            }
        
        # Resolve PAA question URLs
        paa_questions = []
        for paa in serp_data_full.get("paa_questions", []):
            if not isinstance(paa, dict):
                continue
            paa_url = paa.get("source_url", "")
            if paa_url and paa_url.startswith("https://vertexaisearch.cloud.google.com/"):
                resolved_paa_data = resolved_urls.get(paa_url, {})
                if isinstance(resolved_paa_data, dict):
                    paa_url = resolved_paa_data.get("resolved_url", paa_url)
            
            paa_questions.append({
                "question": paa.get("question", ""),
                "answer_snippet": paa.get("answer_snippet"),
                "source_url": paa_url,  # Use resolved URL
                "source_domain": paa.get("source_domain", ""),
                "source_title": paa.get("source_title"),
            })
        
        return {
            "keyword": keyword,
            "search_date": datetime.now().isoformat(),
            "country": country,
            "language": language,
            "organic_results": organic_results,
            "featured_snippet": featured_snippet,
            "paa_questions": paa_questions,
            "related_searches": serp_data_full.get("related_searches", []),
            "image_pack_present": serp_data_full.get("image_pack_present", False),
            "video_results": serp_data_full.get("video_results", []),
            "ads_count": serp_data_full.get("ads_count", 0),
            "ads_top_domains": serp_data_full.get("ads_top_domains", []),
            "avg_word_count": serp_data_full.get("avg_word_count", 0),
            "common_content_types": serp_data_full.get("common_content_types", []),
            "big_brands_count": serp_data_full.get("big_brands_count", 0),
            "avg_domain_authority": serp_data_full.get("avg_domain_authority", 0.0),
            "weakest_position": serp_data_full.get("weakest_position"),
            "content_gaps_identified": serp_data_full.get("content_gaps_identified", []),
            "differentiation_opportunities": serp_data_full.get("differentiation_opportunities", []),
        }
    
    def _is_big_brand(self, domain: str) -> bool:
        """Check if domain is a big brand."""
        big_brands = [
            "forbes.com", "nytimes.com", "washingtonpost.com", "wsj.com",
            "techcrunch.com", "theverge.com", "wired.com", "cnet.com",
            "capterra.com", "g2.com", "trustpilot.com", "softwareadvice.com",
            "getapp.com", "cnet.com", "pcmag.com", "zdnet.com",
        ]
        domain_lower = domain.lower().replace("www.", "")
        return any(brand in domain_lower for brand in big_brands)
    
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
    
    def _is_big_brand(self, domain: str) -> bool:
        """Check if domain is a big brand."""
        big_brands = [
            "forbes.com", "nytimes.com", "washingtonpost.com", "wsj.com",
            "techcrunch.com", "theverge.com", "wired.com", "cnet.com",
            "capterra.com", "g2.com", "trustpilot.com", "softwareadvice.com",
            "getapp.com", "cnet.com", "pcmag.com", "zdnet.com",
        ]
        domain_lower = domain.lower().replace("www.", "")
        return any(brand in domain_lower for brand in big_brands)

