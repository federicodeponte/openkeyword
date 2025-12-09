"""
Core keyword generation using Google Gemini + SE Ranking gap analysis + Deep Research + SERP Analysis
"""

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from typing import Optional

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import (
    Cluster,
    CompanyInfo,
    GenerationConfig,
    GenerationResult,
    Keyword,
    KeywordStatistics,
)

logger = logging.getLogger(__name__)

# Lazy imports for optional features
_research_engine = None
_serp_analyzer = None

def _get_research_engine(api_key: str, model: str):
    """Lazily initialize research engine."""
    global _research_engine
    if _research_engine is None:
        from .researcher import ResearchEngine
        _research_engine = ResearchEngine(api_key=api_key, model=model)
    return _research_engine

def _get_serp_analyzer(language: str, country: str, gemini_api_key: str = None):
    """
    Lazily initialize SERP analyzer.
    
    Uses Gemini SERP by default (FREE). DataForSEO is legacy/optional.
    """
    global _serp_analyzer
    if _serp_analyzer is None:
        import os
        
        # Default to Gemini SERP (FREE, native Google Search grounding)
        logger.info("Using Gemini SERP with native Google Search grounding")
        from .gemini_serp_analyzer import GeminiSerpAnalyzer
        api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY required for SERP analysis. "
                "This uses Gemini's native Google Search grounding (FREE)."
            )
        _serp_analyzer = GeminiSerpAnalyzer(
            gemini_api_key=api_key,
            language=language,
            country=country
        )
    return _serp_analyzer

# Valid intent types
VALID_INTENTS = {"transactional", "commercial", "comparison", "informational", "question"}

# Broad keyword patterns to filter out (agency mode)
BROAD_PATTERNS = [
    r"^what is \w+$",  # "what is AEO" - too basic
    r"^\w+ vs \w+$",   # "AEO vs SEO" - too broad
    r"^best \w+$",     # "best tools" - too generic
    r"^top \w+$",      # "top companies" - too generic
    r"^\w+ guide$",    # "AEO guide" - too basic
    r"^\w+ definition$",  # "X definition"
    r"^\w+ meaning$",     # "X meaning"
]


class KeywordGenerator:
    """
    AI-powered keyword generator using Google Gemini + SE Ranking.

    Features:
    - AI keyword generation with diverse intents
    - SE Ranking gap analysis (competitor keywords)
    - Company-fit scoring
    - Semantic clustering
    - Intelligent deduplication
    - Multi-language support (any language)
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        seranking_api_key: Optional[str] = None,
        model: str = "gemini-3-pro-preview",
    ):
        """
        Initialize the keyword generator.

        Args:
            gemini_api_key: Google Gemini API key (or set GEMINI_API_KEY env var)
            seranking_api_key: SE Ranking API key for gap analysis (optional)
            model: Gemini model to use (default: gemini-1.5-flash)
        """
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY env var or pass gemini_api_key."
            )

        # Store as both for compatibility
        self.gemini_api_key = self.api_key

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model

        # SE Ranking client (optional - for gap analysis)
        self.seranking_api_key = seranking_api_key or os.getenv("SERANKING_API_KEY")
        self.seranking_client = None

        if self.seranking_api_key:
            try:
                from .seranking_client import SEORankingAPIClient

                self.seranking_client = SEORankingAPIClient(self.seranking_api_key)
                logger.info("SE Ranking client initialized for gap analysis")
            except Exception as e:
                logger.warning(f"SE Ranking client initialization failed: {e}")

    async def generate(
        self,
        company_info: CompanyInfo,
        config: Optional[GenerationConfig] = None,
    ) -> GenerationResult:
        """
        Generate keywords for a company.

        Args:
            company_info: Company information
            config: Generation configuration

        Returns:
            GenerationResult with keywords, clusters, and statistics
        """
        start_time = time.time()
        config = config or GenerationConfig()

        logger.info(f"Generating {config.target_count} keywords for {company_info.name}")
        logger.info(f"Language: {config.language}, Region: {config.region}")
        
        # Research focus mode: agency-level hyper-niche keywords
        if config.research_focus:
            config.enable_research = True  # Force research on
            config.min_word_count = max(config.min_word_count, 4)  # Minimum 4 words
            logger.info("🎯 RESEARCH FOCUS MODE: 70% research, 4+ word minimum, strict filtering")
        
        if config.enable_research:
            logger.info("Deep research ENABLED (Reddit, Quora, forums)")
        if config.enable_serp_analysis:
            logger.info(f"SERP analysis ENABLED (top {config.serp_sample_size} keywords)")

        all_keywords = []

        # PARALLEL STEP 1: Run Research, SERanking, and Autocomplete simultaneously
        # These are independent operations that can run in parallel for speed
        parallel_tasks = []
        
        # Task 1: Deep Research (if enabled) - Reddit, Quora, forums
        if config.enable_research:
            research_ratio = 0.7 if config.research_focus else 0.5
            research_target = int(config.target_count * research_ratio)
            parallel_tasks.append(('research', self._get_research_keywords(company_info, config, research_target)))
        
        # Task 2: SE Ranking gap analysis (if available and company has URL)
        if self.seranking_client and company_info.url:
            parallel_tasks.append(('gap', self._get_gap_keywords(company_info, config)))
        
        # Task 3: Google Autocomplete (if enabled) - can run in parallel with seed keywords
        if config.enable_autocomplete:
            # Use company name/description as seed for autocomplete
            parallel_tasks.append(('autocomplete', self._get_autocomplete_keywords(company_info, config)))
        
        # Execute all parallel tasks simultaneously
        logger.info(f"🚀 Running {len(parallel_tasks)} keyword sources in parallel...")
        parallel_results = await asyncio.gather(*[task[1] for task in parallel_tasks], return_exceptions=True)
        
        # Process results
        research_keywords = []
        gap_keywords = []
        autocomplete_keywords = []
        
        for (task_type, _), result in zip(parallel_tasks, parallel_results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️  {task_type} task failed: {result}")
                continue
            
            if task_type == 'research':
                research_keywords = result
                logger.info(f"🔍 Deep research found {len(research_keywords)} hyper-niche keywords")
                all_keywords.extend(research_keywords)
            elif task_type == 'gap':
                gap_keywords = result
                logger.info(f"📊 SE Ranking gap analysis found {len(gap_keywords)} competitor keywords")
                all_keywords.extend(gap_keywords)
            elif task_type == 'autocomplete':
                autocomplete_keywords = result or []
                if autocomplete_keywords:
                    logger.info(f"🔤 Google Autocomplete found {len(autocomplete_keywords)} real user queries")
                    all_keywords.extend(autocomplete_keywords)

        # Step 2: AI keyword generation (fill remaining slots)
        existing_count = len(research_keywords) + len(gap_keywords) + len(autocomplete_keywords)
        # In research focus mode, only generate AI keywords if we don't have enough research
        if config.research_focus:
            # Only fill gap if research didn't return enough
            ai_target = max(0, config.target_count - existing_count)
            if existing_count >= config.target_count * 0.5:
                ai_target = min(ai_target, config.target_count // 5)  # Max 20% AI backup
        else:
            ai_target = max(config.target_count - existing_count, config.target_count // 3)
        
        if ai_target > 0:
            ai_keywords = await self._generate_ai_keywords(company_info, config, ai_target)
            logger.info(f"🤖 Generated {len(ai_keywords)} AI keywords")
            all_keywords.extend(ai_keywords)
        else:
            logger.info("✅ Skipping AI generation - parallel sources provided enough keywords")

        if not all_keywords:
            return GenerationResult(
                keywords=[],
                clusters=[],
                statistics=KeywordStatistics(total=0),
                processing_time_seconds=time.time() - start_time,
            )

        # Step 3: Fast deduplicate (exact + token signature)
        all_keywords, dup_count = self._deduplicate_fast(all_keywords)
        logger.info(f"After fast dedup: {len(all_keywords)} keywords ({dup_count} removed)")

        # Step 3.5: Add hyper-niche variations (geo/industry targeting like openanalytics)
        # Add BEFORE scoring so they get proper company-fit scores
        if len(all_keywords) > 0:
            niche_variations = self._generate_hyper_niche_variations(
                all_keywords, company_info, config
            )
            if niche_variations:
                all_keywords.extend(niche_variations)
                logger.info(f"🔍 Added {len(niche_variations)} hyper-niche variations (geo/industry)")
                # Re-dedupe after adding niche variations
                all_keywords, _ = self._deduplicate_fast(all_keywords)

        # Step 4: Score keywords (includes hyper-niche variations, bonus keywords, and gap keywords)
        # Score ALL keywords for company-fit (including gap keywords)
        all_keywords = await self._score_keywords(all_keywords, company_info)
        logger.info(f"Scored {len(all_keywords)} keywords (including gap and bonus keywords)")

        # Step 5: AI semantic deduplication (removes "sign up X" vs "sign up for X" etc.)
        all_keywords = await self._deduplicate_semantic(all_keywords)
        logger.info(f"After AI semantic dedup: {len(all_keywords)} keywords")

        # Step 6: Filter by score
        all_keywords = [kw for kw in all_keywords if kw.get("score", 0) >= config.min_score]
        logger.info(f"After score filter: {len(all_keywords)} keywords")

        # Step 6b: Filter by word count (hyper-niche mode)
        if config.min_word_count > 2:
            before_count = len(all_keywords)
            all_keywords = [
                kw for kw in all_keywords 
                if len(kw.get("keyword", "").split()) >= config.min_word_count
            ]
            logger.info(f"After word count filter ({config.min_word_count}+ words): {len(all_keywords)} keywords ({before_count - len(all_keywords)} removed)")

        # Step 6c: Filter broad patterns (research focus mode)
        if config.research_focus:
            before_count = len(all_keywords)
            all_keywords = self._filter_broad_keywords(all_keywords)
            logger.info(f"After broad pattern filter: {len(all_keywords)} keywords ({before_count - len(all_keywords)} removed)")

        # Step 7: Cluster keywords
        if config.enable_clustering and len(all_keywords) > 0:
            all_keywords = await self._cluster_keywords(
                all_keywords, company_info, config.cluster_count
            )

        # Step 8: SERP Analysis (if enabled) - enriches with AEO scores
        serp_analyses = {}
        bonus_keywords = []
        if config.enable_serp_analysis:
            serp_analyses, bonus_keywords = await self._analyze_serp(
                all_keywords, config
            )
            logger.info(f"🔍 SERP analysis complete. Found {len(bonus_keywords)} bonus keywords from PAA/related")
            
            # Add bonus keywords and score them properly for company-fit
            if bonus_keywords:
                bonus_kw_dicts = [
                    {"keyword": kw, "intent": "question" if "?" in kw else "informational", 
                     "score": 0, "source": "serp_paa", "is_question": "?" in kw}
                    for kw in bonus_keywords[:config.target_count // 4]  # Limit bonus
                ]
                all_keywords.extend(bonus_kw_dicts)
                # Re-dedupe after adding bonus
                all_keywords, _ = self._deduplicate_fast(all_keywords)
                
                # Score bonus keywords properly for company-fit (they were added after Step 4 scoring)
                if bonus_kw_dicts:
                    scored_bonus = await self._score_keywords(bonus_kw_dicts, company_info)
                    # Update scores in all_keywords
                    bonus_score_map = {kw["keyword"]: kw["score"] for kw in scored_bonus}
                    for kw in all_keywords:
                        if kw.get("source") == "serp_paa" and kw["keyword"] in bonus_score_map:
                            kw["score"] = bonus_score_map[kw["keyword"]]
                    logger.info(f"✅ Scored {len(scored_bonus)} bonus keywords for company-fit")

        # Step 9: Limit to target count
        all_keywords = all_keywords[: config.target_count]

        # Step 10: Volume lookup (DataForSEO Keywords Data API)
        volume_data = {}
        if config.enable_volume_lookup:
            volume_data = await self._lookup_volumes(
                [kw["keyword"] for kw in all_keywords],
                config.language,
                config.region
            )
            logger.info(f"📈 Volume lookup: got data for {len(volume_data)}/{len(all_keywords)} keywords")

        # Step 11: Generate content briefs (if enabled) - PARALLEL for performance
        content_briefs = {}
        if config.enable_enhanced_capture and config.enable_content_briefs:
            # Generate briefs for top keywords
            top_keywords_for_briefs = all_keywords[:config.content_brief_count]
            logger.info(f"📝 Generating content briefs for {len(top_keywords_for_briefs)} keywords...")
            
            # Generate briefs in parallel for performance
            brief_tasks = []
            for kw in top_keywords_for_briefs:
                kw_text = kw["keyword"]
                research_data = kw.get("_research_data")
                serp_analysis = serp_analyses.get(kw_text)
                serp_data = getattr(serp_analysis, "_complete_serp_data", None) if serp_analysis else None
                
                brief_tasks.append(
                    self._generate_content_brief(
                        keyword=kw_text,
                        research_data=research_data,
                        serp_data=serp_data,
                        company_info=company_info,
                    )
                )
            
            # Execute all brief generations in parallel
            brief_results = await asyncio.gather(*brief_tasks, return_exceptions=True)
            
            # Process results
            for kw, brief_result in zip(top_keywords_for_briefs, brief_results):
                kw_text = kw["keyword"]
                if isinstance(brief_result, Exception):
                    logger.warning(f"Content brief generation failed for '{kw_text}': {brief_result}")
                elif brief_result:
                    content_briefs[kw_text] = brief_result
            
            logger.info(f"✅ Generated {len(content_briefs)}/{len(top_keywords_for_briefs)} content briefs")

        # Step 12: Google Trends enrichment (if enabled) - FREE trend data
        trends_data_map = {}
        if config.enable_google_trends and len(all_keywords) > 0:
            trends_data_map = await self._enrich_with_trends(
                [kw["keyword"] for kw in all_keywords[:30]],  # Top 30 only (rate limits)
                config
            )
            logger.info(f"📊 Enriched {len(trends_data_map)} keywords with Google Trends data")

        # Step 13: Generate citations (if enabled)
        from .citation_generator import CitationGenerator
        from .models import ResearchData, ResearchSource, ContentBrief, ContentBriefSource, CompleteSERPData, SERPRanking, FeaturedSnippetData, PAAQuestion, GoogleTrendsData, AutocompleteData
        
        citation_generator = CitationGenerator()

        # Build result with SERP and volume enrichment
        keyword_objects = []
        for kw in all_keywords:
            kw_text = kw["keyword"]
            serp_data = serp_analyses.get(kw_text)
            vol_data = volume_data.get(kw_text.lower(), {})
            
            # Volume comes from DataForSEO if enabled, else from gap analysis
            volume = vol_data.get("volume", 0) if vol_data else kw.get("volume", 0)
            difficulty = vol_data.get("difficulty", 50) if vol_data else kw.get("difficulty", 50)
            
            # Enhanced data capture
            research_data_obj = None
            content_brief_obj = None
            serp_data_obj = None
            citations_list = []
            research_summary = None
            research_source_urls = []
            top_ranking_urls = []
            featured_snippet_url = None
            paa_questions_with_urls = []
            
            if config.enable_enhanced_capture:
                # Build ResearchData object (only for research-sourced keywords)
                research_data_dict = kw.get("_research_data")
                # Only set research_data if keyword is actually research-sourced
                is_research_sourced = "research" in kw.get("source", "").lower()
                if research_data_dict and is_research_sourced:
                    sources = []
                    for source_dict in research_data_dict.get("sources", [])[:config.research_sources_per_keyword]:
                        # Validate source_dict before creating ResearchSource
                        # Ensure required fields exist
                        if not source_dict.get("quote") and not source_dict.get("url"):
                            continue  # Skip sources with no quote or URL
                        
                        # Ensure URL is valid if present
                        url = source_dict.get("url", "")
                        if url and not (url.startswith("http://") or url.startswith("https://")):
                            source_dict["url"] = ""  # Clear invalid URL
                        
                        try:
                            sources.append(ResearchSource(**source_dict))
                        except Exception as e:
                            logger.warning(f"Failed to create ResearchSource for '{kw_text}': {e}")
                            continue
                    
                    research_data_obj = ResearchData(
                        keyword=kw_text,
                        sources=sources,
                        total_sources_found=research_data_dict.get("total_sources", len(sources)),
                        platforms_searched=research_data_dict.get("platforms", []),
                        most_mentioned_pain_points=research_data_dict.get("pain_points", []),
                        common_solutions_mentioned=research_data_dict.get("solutions", []),
                        sentiment_breakdown=research_data_dict.get("sentiment_breakdown", {}),
                    )
                    
                    # Generate research summary (top 3 quotes)
                    if sources:
                        top_quotes = []
                        for s in sources[:3]:
                            if s.quote:
                                platform = s.platform or "source"
                                quote_short = s.quote[:100] + "..." if len(s.quote) > 100 else s.quote
                                top_quotes.append(f"{platform}: '{quote_short}'")
                        research_summary = " | ".join(top_quotes)
                    
                    # Extract URLs
                    research_source_urls = [s.url for s in sources if s.url]
                
                # Build ContentBrief object
                content_brief_dict = content_briefs.get(kw_text)
                if content_brief_dict:
                    # Convert sources to ContentBriefSource objects
                    sources_list = content_brief_dict.get("sources", [])
                    source_objects = []
                    for src_dict in sources_list:
                        try:
                            source_objects.append(ContentBriefSource(**src_dict))
                        except Exception as e:
                            logger.warning(f"Failed to create ContentBriefSource: {e}")
                            continue
                    
                    # Create ContentBrief with sources
                    content_brief_obj = ContentBrief(
                        **{k: v for k, v in content_brief_dict.items() if k != "sources"},
                        sources=source_objects
                    )
                
                # Build CompleteSERPData object
                serp_analysis_obj = serp_analyses.get(kw_text)
                complete_serp_data_dict = getattr(serp_analysis_obj, "_complete_serp_data", None) if serp_analysis_obj else None
                if complete_serp_data_dict:
                    # Convert to Pydantic models
                    organic_results_objs = []
                    for result_dict in complete_serp_data_dict.get("organic_results", []):
                        organic_results_objs.append(SERPRanking(**result_dict))
                    
                    featured_snippet_obj = None
                    if complete_serp_data_dict.get("featured_snippet"):
                        featured_snippet_obj = FeaturedSnippetData(**complete_serp_data_dict["featured_snippet"])
                        featured_snippet_url = featured_snippet_obj.source_url
                    
                    paa_questions_objs = []
                    for paa_dict in complete_serp_data_dict.get("paa_questions", []):
                        paa_questions_objs.append(PAAQuestion(**paa_dict))
                        paa_questions_with_urls.append({
                            "question": paa_dict.get("question", ""),
                            "url": paa_dict.get("source_url", ""),
                        })
                    
                    # Ensure numeric fields are not None
                    avg_da = complete_serp_data_dict.get("avg_domain_authority")
                    if avg_da is None:
                        avg_da = 0.0
                    
                    avg_wc = complete_serp_data_dict.get("avg_word_count")
                    if avg_wc is None:
                        avg_wc = 0
                    
                    big_brands = complete_serp_data_dict.get("big_brands_count")
                    if big_brands is None:
                        big_brands = 0
                    
                    serp_data_obj = CompleteSERPData(
                        keyword=kw_text,
                        search_date=complete_serp_data_dict.get("search_date", ""),
                        country=complete_serp_data_dict.get("country", config.region),
                        language=complete_serp_data_dict.get("language", config.language),
                        organic_results=organic_results_objs,
                        featured_snippet=featured_snippet_obj,
                        paa_questions=paa_questions_objs,
                        related_searches=complete_serp_data_dict.get("related_searches", []),
                        image_pack_present=complete_serp_data_dict.get("image_pack_present", False),
                        video_results=complete_serp_data_dict.get("video_results", []),
                        ads_count=complete_serp_data_dict.get("ads_count", 0),
                        ads_top_domains=complete_serp_data_dict.get("ads_top_domains", []),
                        avg_word_count=avg_wc,
                        common_content_types=complete_serp_data_dict.get("common_content_types", []),
                        big_brands_count=big_brands,
                        avg_domain_authority=avg_da,
                        weakest_position=complete_serp_data_dict.get("weakest_position"),
                        content_gaps_identified=complete_serp_data_dict.get("content_gaps_identified", []),
                        differentiation_opportunities=complete_serp_data_dict.get("differentiation_opportunities", []),
                    )
                    
                    # Extract top ranking URLs (only valid HTTP(S) URLs)
                    top_ranking_urls = [
                        r.url for r in organic_results_objs[:10]
                        if r.url and (r.url.startswith("http://") or r.url.startswith("https://"))
                    ]
                
                # Generate citations (only if we have data to cite)
                citations_list = []
                if config.enable_citations and (research_data_obj or complete_serp_data_dict):
                    try:
                        # Convert ResearchData object to dict if needed
                        research_data_for_citations = None
                        if research_data_obj:
                            research_data_for_citations = {
                                "sources": [s.model_dump() for s in research_data_obj.sources]
                            }
                        
                        citations_list = citation_generator.generate_citations(
                            research_data=research_data_for_citations,
                            serp_data=complete_serp_data_dict,
                            keyword=kw_text,
                        )
                        # Validate citations have required fields
                        valid_citations = []
                        for cit in citations_list:
                            if cit.get("url") and cit.get("format_apa"):
                                valid_citations.append(cit)
                            else:
                                logger.debug(f"Skipping incomplete citation for '{kw_text}'")
                        citations_list = valid_citations
                    except Exception as e:
                        logger.warning(f"Citation generation failed for '{kw_text}': {e}")
                        citations_list = []
            
            # Only include research_data if keyword is research-sourced (don't set to None)
            final_research_data = research_data_obj if (research_data_obj and "research" in kw.get("source", "").lower()) else None
            
            # Build keyword object - only include research_data if it exists
            kw_dict = {
                "keyword": kw_text,
                "intent": kw.get("intent", "informational"),
                "score": kw.get("score", 0),
                "cluster_name": kw.get("cluster_name"),
                "is_question": kw.get("is_question", False),
                "volume": volume,
                "difficulty": difficulty,
                "source": kw.get("source", "ai_generated"),
                # SERP/AEO fields
                "aeo_opportunity": serp_data.features.aeo_opportunity if serp_data else 0,
                "has_featured_snippet": serp_data.features.has_featured_snippet if serp_data else False,
                "has_paa": serp_data.features.has_paa if serp_data else False,
                "serp_analyzed": serp_data is not None,
                # Enhanced data capture fields
                "content_brief": content_brief_obj,
                "serp_data": serp_data_obj,
                "research_summary": research_summary if research_summary else None,
                "research_source_urls": research_source_urls,
                "top_ranking_urls": top_ranking_urls,
                "featured_snippet_url": featured_snippet_url,
                "paa_questions_with_urls": paa_questions_with_urls,
                "citations": citations_list,
            }
            
            # Only add research_data if it exists (not None)
            if final_research_data:
                kw_dict["research_data"] = final_research_data
            
            # Add trends_data if available
            if kw_text in trends_data_map:
                kw_dict["trends_data"] = trends_data_map[kw_text]
            
            keyword_objects.append(Keyword(**kw_dict))

        # Build clusters
        clusters_map = defaultdict(list)
        for kw in keyword_objects:
            if kw.cluster_name:
                clusters_map[kw.cluster_name].append(kw.keyword)

        clusters = [Cluster(name=name, keywords=kws) for name, kws in clusters_map.items()]

        # Calculate statistics
        stats = self._calculate_statistics(keyword_objects, dup_count)

        processing_time = time.time() - start_time
        logger.info(
            f"Generation complete: {len(keyword_objects)} keywords in {processing_time:.1f}s"
        )

        return GenerationResult(
            keywords=keyword_objects,
            clusters=clusters,
            statistics=stats,
            processing_time_seconds=processing_time,
        )

    async def _get_gap_keywords(
        self, company_info: CompanyInfo, config: GenerationConfig
    ) -> list[dict]:
        """Get keywords from SE Ranking gap analysis."""
        if not self.seranking_client or not company_info.url:
            return []

        try:
            domain = self.seranking_client.extract_domain(company_info.url)
            competitors = [
                self.seranking_client.extract_domain(c) for c in company_info.competitors
            ] if company_info.competitors else None

            # Run gap analysis (sync, wrapped in thread)
            gaps = await asyncio.to_thread(
                self.seranking_client.analyze_content_gaps,
                domain=domain,
                competitors=competitors,
                source=config.region,
                max_competitors=3,
            )

            # Convert to our format
            keywords = []
            for gap in gaps:
                keywords.append({
                    "keyword": gap.get("keyword", ""),
                    "intent": gap.get("intent", "informational"),
                    "volume": gap.get("volume", 0),
                    "difficulty": gap.get("difficulty", 50),
                    "score": gap.get("aeo_score", 50),
                    "is_question": gap.get("intent") == "question",
                    "source": "gap_analysis",
                })

            return keywords

        except Exception as e:
            logger.error(f"Gap analysis failed: {e}")
            return []

    async def _get_research_keywords(
        self, company_info: CompanyInfo, config: GenerationConfig, target_count: int = None
    ) -> list[dict]:
        """
        Get keywords from deep research (Reddit, Quora, forums).

        Uses Google Search grounding to find real user discussions
        and extract hyper-niche keywords and questions.
        """
        try:
            # Initialize research engine
            researcher = _get_research_engine(self.api_key, self.model_name)
            
            # Use provided target or default to 50%
            research_target = target_count or (config.target_count // 2)

            # Run deep research
            research_keywords = await researcher.discover_keywords(
                company_name=company_info.name,
                industry=company_info.industry or "general",
                services=company_info.services,
                products=company_info.products,
                target_location=company_info.target_location or "United States",
                language=config.language,
                target_count=research_target,
            )

            # Normalize source names
            for kw in research_keywords:
                source = kw.get("source", "research")
                if source in ("reddit", "research_reddit"):
                    kw["source"] = "research_reddit"
                elif source in ("quora_paa", "research_quora"):
                    kw["source"] = "research_quora"
                elif source in ("niche_research", "research_niche"):
                    kw["source"] = "research_niche"
                else:
                    kw["source"] = "research"

            # Aggregate research data if enhanced capture enabled
            research_data_by_keyword = {}
            if config.enable_enhanced_capture:
                aggregated = researcher._aggregate_research_data(research_keywords)
                research_data_by_keyword = aggregated

            # Store research data mapping for later use
            for kw in research_keywords:
                keyword = kw.get("keyword", "")
                if keyword in research_data_by_keyword:
                    kw["_research_data"] = research_data_by_keyword[keyword]

            return research_keywords

        except Exception as e:
            logger.error(f"Deep research failed: {e}")
            return []

    async def _analyze_serp(
        self, keywords: list[dict], config: GenerationConfig
    ) -> tuple[dict, list[str]]:
        """
        Analyze SERP features for top keywords using DataForSEO.
        
        Returns:
            Tuple of (serp_analyses dict, bonus_keywords list)
        """
        if not keywords:
            return {}, []
        
        try:
            # Get SERP analyzer (Gemini native by default)
            analyzer = _get_serp_analyzer(
                language=config.language[:2] if len(config.language) > 2 else config.language,
                country=config.region,
                gemini_api_key=self.gemini_api_key,
            )
            
            # Only analyze top N keywords (SERP calls cost money)
            top_keywords = [kw["keyword"] for kw in keywords[:config.serp_sample_size]]
            
            logger.info(f"Analyzing SERP for {len(top_keywords)} top keywords...")
            
            # Run SERP analysis
            analyses, bonus = await analyzer.analyze_keywords(
                top_keywords,
                extract_bonus=True,
            )
            
            # Log findings
            snippets = sum(1 for a in analyses.values() if a.features.has_featured_snippet)
            paa_count = sum(1 for a in analyses.values() if a.features.has_paa)
            avg_aeo = sum(a.features.aeo_opportunity for a in analyses.values()) / len(analyses) if analyses else 0
            
            logger.info(f"SERP results: {snippets} featured snippets, {paa_count} PAA sections, avg AEO score: {avg_aeo:.0f}")
            
            # Build complete SERP data if enhanced capture enabled
            complete_serp_data = {}
            if config.enable_enhanced_capture and analyzer:
                # Build all SERP data in parallel (includes URL resolution and meta tag extraction)
                build_tasks = []
                build_keywords = []
                for keyword, analysis in analyses.items():
                    # Check if serp_data_full has actual data (not just empty dict)
                    has_full_data = (
                        analysis.serp_data_full and 
                        isinstance(analysis.serp_data_full, dict) and
                        (analysis.serp_data_full.get("organic_results") or 
                         analysis.serp_data_full.get("featured_snippet") or
                         analysis.serp_data_full.get("paa_questions"))
                    )
                    
                    if has_full_data:
                        build_tasks.append(
                            analyzer._build_complete_serp_data(
                                serp_data_full=analysis.serp_data_full,
                                keyword=keyword,
                                country=config.region,
                                language=config.language[:2] if len(config.language) > 2 else config.language,
                            )
                        )
                        build_keywords.append(keyword)
                
                # Execute all builds in parallel (includes URL resolution)
                if build_tasks:
                    logger.info(f"Building SERP data for {len(build_tasks)} keywords (resolving URLs and extracting meta tags)...")
                    built_results = await asyncio.gather(*build_tasks, return_exceptions=True)
                    for kw, result in zip(build_keywords, built_results):
                        if isinstance(result, Exception):
                            logger.warning(f"Failed to build SERP data for '{kw}': {result}")
                        else:
                            complete_serp_data[kw] = result
                
                # Fallback: Build from features if serp_data_full is missing
                for keyword, analysis in analyses.items():
                    if keyword not in complete_serp_data and analysis.features and not analysis.error:
                        try:
                            # Fallback: Build from features if serp_data_full is missing or empty
                            # This happens when Gemini returns basic data but not full structure
                            logger.debug(f"Building SERP data from features for '{keyword}' (serp_data_full missing/empty)")
                            # Create minimal serp_data_full from features
                            minimal_serp_data = {
                                "organic_results": [],
                                "featured_snippet": {
                                    "type": "paragraph",
                                    "content": analysis.features.featured_snippet_text or "",
                                    "source_url": analysis.features.featured_snippet_url or "",
                                    "source_domain": "",
                                } if analysis.features.has_featured_snippet else None,
                                "paa_questions": [
                                    {"question": q, "answer_snippet": "", "source_url": "", "source_domain": ""}
                                    for q in analysis.features.paa_questions
                                ],
                                "related_searches": analysis.features.related_searches or [],
                                "avg_word_count": 0,
                                "common_content_types": [],
                                "big_brands_count": 0,
                                "avg_domain_authority": 0.0,
                                "content_gaps_identified": [],
                                "differentiation_opportunities": [],
                            }
                            complete_serp_data[keyword] = await analyzer._build_complete_serp_data(
                                serp_data_full=minimal_serp_data,
                                keyword=keyword,
                                country=config.region,
                                language=config.language[:2] if len(config.language) > 2 else config.language,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to build complete SERP data for '{keyword}': {e}")
                    elif keyword not in complete_serp_data:
                        logger.debug(f"Skipping SERP data build for '{keyword}' (no features or has error)")
            
            # Store complete SERP data in analyses for later use
            for keyword, analysis in analyses.items():
                if keyword in complete_serp_data:
                    analysis._complete_serp_data = complete_serp_data[keyword]
            
            return analyses, bonus
            
        except Exception as e:
            logger.error(f"SERP analysis failed: {e}")
            return {}, []

    async def _lookup_volumes(
        self, keywords: list[str], language: str, region: str
    ) -> dict[str, dict]:
        """
        Look up search volumes and difficulty using DataForSEO Keywords Data API.
        
        Args:
            keywords: List of keywords to look up
            language: Language code (e.g., "english" or "en")
            region: Country code (e.g., "us", "de")
        
        Returns:
            Dict mapping keyword (lowercase) -> {volume, difficulty, cpc, competition_level}
        """
        if not keywords:
            return {}
        
        try:
            from .dataforseo_client import DataForSEOClient
            
            client = DataForSEOClient()
            if not client.is_configured():
                logger.warning("DataForSEO not configured - skipping volume lookup")
                return {}
            
            # Map language name to code
            lang_code = language[:2].lower() if len(language) > 2 else language.lower()
            
            # Get keyword data in batches (API limit is 1000 per request)
            all_data = {}
            batch_size = 700  # Leave some margin
            
            for i in range(0, len(keywords), batch_size):
                batch = keywords[i:i + batch_size]
                logger.info(f"Looking up volumes for batch {i//batch_size + 1} ({len(batch)} keywords)...")
                
                batch_data = await client.get_keyword_data(
                    keywords=batch,
                    language=lang_code,
                    country=region.lower(),
                )
                all_data.update(batch_data)
            
            return all_data
            
        except Exception as e:
            logger.error(f"Volume lookup failed: {e}")
            return {}

    async def _generate_ai_keywords(
        self, company_info: CompanyInfo, config: GenerationConfig, target_count: int
    ) -> list[dict]:
        """Generate keywords using Gemini in parallel batches."""
        # Build company context
        context_parts = [f"Company: {company_info.name}"]
        if company_info.industry:
            context_parts.append(f"Industry: {company_info.industry}")
        if company_info.description:
            context_parts.append(f"Description: {company_info.description}")
        if company_info.services:
            context_parts.append(f"Services: {', '.join(company_info.services)}")
        if company_info.products:
            context_parts.append(f"Products: {', '.join(company_info.products)}")
        if company_info.brands:
            context_parts.append(f"Brands: {', '.join(company_info.brands)}")
        if company_info.target_location:
            context_parts.append(f"Location: {company_info.target_location}")
        if company_info.target_audience:
            context_parts.append(f"Target Audience: {company_info.target_audience}")

        company_context = "\n".join(context_parts)

        # Over-generate to account for deduplication and filtering
        buffer_count = int(target_count * 2.5)
        batch_size = 15
        num_batches = (buffer_count + batch_size - 1) // batch_size

        logger.info(f"Generating {buffer_count} AI keywords in {num_batches} batches")

        # Generate batches in parallel
        tasks = [
            self._generate_batch(
                company_context, batch_size, i + 1, num_batches, config.language, config.region
            )
            for i in range(num_batches)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_keywords = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch failed: {result}")
            elif result:
                all_keywords.extend(result)

        return all_keywords

    def _generate_hyper_niche_variations(
        self, keywords: list[dict], company_info: CompanyInfo, config: GenerationConfig
    ) -> list[dict]:
        """
        Generate hyper-niche LONG-TAIL keyword variations with geo/industry targeting.
        
        Emphasizes LONG-TAIL keywords (4+ words) with multiple modifiers:
        - Geographic: "best [product] [country]"
        - Industry: "best [product] for [industry]"
        - Company size: "best [product] for [size]"
        - Use cases: "how to use [product] for [use case]"
        - Questions: "what is [product] for [industry]"
        - Combined: Multiple modifiers for maximum specificity
        """
        variations = []
        
        # Extract SERVICES (solutions) for targeting - SKIP products (avoid product names)
        services = company_info.services or []
        
        # Also extract pain points and use cases for problem-focused keywords
        pain_points = company_info.pain_points or []
        use_cases = company_info.use_cases or []
        
        if not services:
            return variations
        
        # Use only top 3 services (most important ones)
        all_offerings = services[:3]
        
        # Extract industry (clean to 2 words max)
        industry = None
        if company_info.industry:
            industry_words = company_info.industry.split()[:2]
            industry = " ".join(industry_words).lower()
        
        # Extract company size from target_audience
        company_size = None
        if company_info.target_audience:
            audience_lower = company_info.target_audience.lower()
            if any(x in audience_lower for x in ["small business", "smb", "sme", "startup"]):
                company_size = "small businesses"
            elif any(x in audience_lower for x in ["mid-size", "mid-market", "50-500", "100-500"]):
                company_size = "mid-size companies"
            elif any(x in audience_lower for x in ["enterprise", "500+", "fortune 500", "large"]):
                company_size = "enterprise"
        
        # Determine if we should add geo modifier (skip for US/global)
        use_geo = False
        geo_suffix = ""
        if company_info.target_location:
            location_lower = company_info.target_location.lower()
            if not any(x in location_lower for x in ["us", "united states", "usa", "global", "worldwide"]):
                geo_suffix = f" {company_info.target_location}"
                use_geo = True
        
        # Generate LONG-TAIL variations for ALL products/services (not just top 3)
        for offering in all_offerings[:5]:  # Increased from 3 to 5
            # Clean offering name (max 4 words)
            offering_words = offering.split()[:4]
            clean_offering = " ".join(offering_words).lower()
            
            if len(clean_offering) > 50:
                continue
            
            # ===== LONG-TAIL QUESTION VARIATIONS (4+ words) =====
            question_patterns = []
            if industry:
                question_patterns.extend([
                    f"what is {clean_offering} for {industry}",
                    f"how does {clean_offering} work for {industry}",
                    f"why use {clean_offering} for {industry}",
                ])
            if company_size:
                question_patterns.extend([
                    f"what is {clean_offering} for {company_size}",
                    f"how to use {clean_offering} for {company_size}",
                ])
            if use_geo:
                question_patterns.extend([
                    f"what is {clean_offering}{geo_suffix}",
                    f"how to use {clean_offering}{geo_suffix}",
                ])
            # Combined question patterns (longest = most niche)
            if industry and use_geo:
                question_patterns.extend([
                    f"what is {clean_offering} for {industry}{geo_suffix}",
                    f"how to use {clean_offering} for {industry}{geo_suffix}",
                ])
            if industry and company_size:
                question_patterns.extend([
                    f"what is {clean_offering} for {industry} {company_size}",
                    f"how to use {clean_offering} for {industry} {company_size}",
                ])
            if industry and company_size and use_geo:
                question_patterns.append(
                    f"what is {clean_offering} for {industry} {company_size}{geo_suffix}"
                )
            
            for pattern in question_patterns:
                if len(pattern.split()) >= 4 and len(pattern) <= 80:  # Long-tail: 4+ words
                    variations.append({
                        "keyword": pattern,
                        "intent": "question",
                        "score": 95,  # High score for long-tail questions
                        "source": "hyper_niche_question",
                        "is_question": True,
                    })
            
            # ===== LONG-TAIL COMMERCIAL VARIATIONS (4+ words) =====
            # Base long-tail patterns
            long_tail_patterns = [
                f"best {clean_offering} for {industry}" if industry else None,
                f"best {clean_offering} for {company_size}" if company_size else None,
                f"best {clean_offering}{geo_suffix}" if use_geo else None,
            ]
            
            # Combined long-tail patterns (multiple modifiers = more niche)
            if industry and use_geo:
                long_tail_patterns.extend([
                    f"best {clean_offering} for {industry}{geo_suffix}",
                    f"top {clean_offering} for {industry}{geo_suffix}",
                    f"{clean_offering} for {industry}{geo_suffix}",
                ])
            if industry and company_size:
                long_tail_patterns.extend([
                    f"best {clean_offering} for {industry} {company_size}",
                    f"top {clean_offering} for {industry} {company_size}",
                ])
            if company_size and use_geo:
                long_tail_patterns.extend([
                    f"best {clean_offering} for {company_size}{geo_suffix}",
                ])
            if industry and company_size and use_geo:
                long_tail_patterns.extend([
                    f"best {clean_offering} for {industry} {company_size}{geo_suffix}",
                    f"top {clean_offering} for {industry} {company_size}{geo_suffix}",
                ])
            
            # Use case specific long-tail
            for use_case in use_cases[:2]:  # Top 2 use cases
                use_case_clean = " ".join(use_case.split()[:3]).lower()  # Max 3 words
                if len(use_case_clean) > 30:
                    continue
                long_tail_patterns.extend([
                    f"best {clean_offering} for {use_case_clean}",
                    f"how to use {clean_offering} for {use_case_clean}",
                ])
                if industry:
                    long_tail_patterns.append(
                        f"best {clean_offering} for {use_case_clean} in {industry}"
                    )
                if use_geo:
                    long_tail_patterns.append(
                        f"best {clean_offering} for {use_case_clean}{geo_suffix}"
                    )
            
            # Pain point specific long-tail
            for pain in pain_points[:2]:  # Top 2 pain points
                pain_clean = " ".join(pain.split()[:3]).lower()  # Max 3 words
                if len(pain_clean) > 30:
                    continue
                long_tail_patterns.extend([
                    f"{clean_offering} to solve {pain_clean}",
                    f"how {clean_offering} solves {pain_clean}",
                ])
            
            for pattern in long_tail_patterns:
                if pattern and len(pattern.split()) >= 4 and len(pattern) <= 80:
                    variations.append({
                        "keyword": pattern,
                        "intent": "commercial",
                        "score": 93,  # High score for long-tail commercial
                        "source": "hyper_niche_longtail",
                    })
            
            # ===== TRANSACTIONAL LONG-TAIL (4+ words) =====
            # Use natural service-buying language: "get [service] services", "find [service] agency"
            transactional_patterns = []
            if industry:
                transactional_patterns.extend([
                    f"get {clean_offering} services for {industry}",
                    f"find {clean_offering} agency for {industry}",
                    f"hire {clean_offering} consultant for {industry}",
                ])
            if company_size:
                transactional_patterns.extend([
                    f"get {clean_offering} services for {company_size}",
                    f"find {clean_offering} agency for {company_size}",
                ])
            if use_geo:
                transactional_patterns.extend([
                    f"get {clean_offering} services{geo_suffix}",
                    f"find {clean_offering} agency{geo_suffix}",
                ])
            if industry and use_geo:
                transactional_patterns.extend([
                    f"get {clean_offering} services for {industry}{geo_suffix}",
                    f"hire {clean_offering} consultant for {industry}{geo_suffix}",
                ])
            if industry and company_size:
                transactional_patterns.extend([
                    f"get {clean_offering} services for {industry} {company_size}",
                ])
            
            for pattern in transactional_patterns:
                if len(pattern.split()) >= 4 and len(pattern) <= 80:
                    variations.append({
                        "keyword": pattern,
                        "intent": "transactional",
                        "score": 94,
                        "source": "hyper_niche_transactional",
                    })
        
        # Filter to only long-tail (4+ words) for maximum niche targeting
        long_tail_variations = [
            v for v in variations 
            if len(v["keyword"].split()) >= 4
        ]
        
        logger.info(f"🔍 Generated {len(long_tail_variations)} hyper-niche LONG-TAIL variations (4+ words)")
        return long_tail_variations

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_batch(
        self,
        company_context: str,
        batch_count: int,
        batch_num: int,
        total_batches: int,
        language: str,
        region: str,
    ) -> list[dict]:
        """Generate a single batch of keywords."""
        # Calculate minimum counts per intent type
        question_min = max(3, int(batch_count * 0.25))
        commercial_min = max(3, int(batch_count * 0.25))
        transactional_min = max(2, int(batch_count * 0.15))
        comparison_min = max(1, int(batch_count * 0.10))

        # Get current date for context
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")  # e.g., "December 2025"
        current_year = datetime.now().year

        # Dynamic language handling - no hardcoded lists
        prompt = f"""Today's date: {current_date}

Generate {batch_count} SEO keywords in {language.upper()} language for the {region.upper()} market.

{company_context}

INTENT TYPES (strict counts):
- {question_min}+ QUESTION: keywords that start with question words in {language} (how, what, why, when, where, which, who, can, should, etc.)
- {transactional_min}+ TRANSACTIONAL: keywords with buying/action intent (book, buy, order, get quote, sign up, etc.)
- {comparison_min}+ COMPARISON: keywords comparing options (vs, versus, alternative, difference, compared to, etc.)
- {commercial_min}+ COMMERCIAL: keywords with commercial intent (best, top, review, pricing, cost, etc.)
- Rest INFORMATIONAL (max 25%): guides, benefits, tips

KEYWORD LENGTH (EMPHASIZE LONG-TAIL):
- 0% SHORT keywords (2-3 words) - SKIP THESE
- 30% MEDIUM keywords (4-5 words)
- 70% LONG keywords (6-8 words) - PRIORITIZE THESE
- Prefer 6-8 word keywords for maximum specificity and niche targeting

RULES:
- ALL keywords must be in {language.upper()} language
- NO single-word keywords
- MINIMUM 4 words per keyword (LONG-TAIL FOCUS)
- PREFER 6-8 word keywords for maximum niche targeting
- Use NATURAL SEARCHER LANGUAGE (how real users search), NOT company product names
- Keywords should solve problems or answer questions, not list products
- Focus on BENEFITS, SOLUTIONS, and USE CASES, not product names
- Include HYPER-LOCAL variations with:
  * Location-specific terms for {region.upper()} market (cities, regions, neighborhoods)
  * Language/market-specific phrasing for {language.upper()} speakers
  * Local competitors, brands, or terminology
  * Regional variations and dialects
- Include current year ({current_year}) in date-specific keywords
- Examples of hyper-local LONG-TAIL: "[service] in [city] for [industry] {current_year}" (6+ words), "[service] for [language] speakers in [region] vs [competitor]" (7+ words)
- LONG-TAIL = MORE SPECIFIC = BETTER TARGETING

Return JSON: {{"keywords": [{{"keyword": "...", "intent": "question|transactional|comparison|commercial|informational", "is_question": true/false}}]}}"""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.8,
                    response_mime_type="application/json",
                ),
            )

            data = self._parse_json_response(response.text)
            keywords_data = data.get("keywords", [])

            if not keywords_data:
                logger.warning(f"Batch {batch_num}: No keywords returned")
                return []

            # Process and validate keywords
            processed = []
            for kw in keywords_data:
                keyword_text = kw.get("keyword", "").strip()
                if not keyword_text:
                    continue

                # Use AI-provided intent, validate it
                ai_intent = kw.get("intent", "informational").lower()
                if ai_intent not in VALID_INTENTS:
                    ai_intent = "informational"

                is_question = kw.get("is_question", False)
                if is_question and ai_intent != "question":
                    ai_intent = "question"

                processed.append({
                    "keyword": keyword_text,
                    "intent": ai_intent,
                    "is_question": is_question,
                    "score": 0,
                    "source": "ai_generated",
                })

            logger.info(f"Batch {batch_num}/{total_batches}: {len(processed)} keywords")
            return processed

        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            raise

    def _deduplicate_fast(self, keywords: list[dict]) -> tuple[list[dict], int]:
        """Fast O(n) deduplication: exact match + token signature grouping."""
        if not keywords:
            return [], 0

        original_count = len(keywords)

        # Phase 1: Exact match removal
        seen_exact = set()
        phase1 = []
        for kw in keywords:
            normalized = kw.get("keyword", "").lower().strip()
            if not normalized:
                continue
            if normalized not in seen_exact:
                seen_exact.add(normalized)
                phase1.append(kw)

        # Phase 2: Token signature grouping
        groups = defaultdict(list)
        for kw in phase1:
            keyword_text = kw.get("keyword", "").lower().strip()
            tokens = tuple(sorted(keyword_text.split()))
            groups[tokens].append(kw)

        # Keep highest scored keyword from each group (or first if not scored yet)
        unique = []
        for token_group in groups.values():
            if len(token_group) == 1:
                unique.append(token_group[0])
            else:
                # Prefer gap_analysis source, then highest score
                gap_kws = [k for k in token_group if k.get("source") == "gap_analysis"]
                if gap_kws:
                    unique.append(gap_kws[0])
                else:
                    best = max(token_group, key=lambda x: x.get("score", 0))
                    unique.append(best)

        duplicate_count = original_count - len(unique)
        return unique, duplicate_count

    def _filter_broad_keywords(self, keywords: list[dict]) -> list[dict]:
        """
        Filter out overly broad keywords using pattern matching.
        
        Removes generic patterns like:
        - "what is X" (too basic)
        - "X vs Y" (too broad)
        - "best X" (too generic)
        """
        filtered = []
        for kw in keywords:
            keyword_text = kw.get("keyword", "").strip()
            
            # Check against broad patterns
            is_broad = False
            for pattern in BROAD_PATTERNS:
                if re.match(pattern, keyword_text, re.IGNORECASE):
                    logger.debug(f"Filtered broad keyword: {keyword_text}")
                    is_broad = True
                    break
            
            # Keep research keywords even if they match patterns (they're real user queries)
            if is_broad and kw.get("source", "").startswith("research"):
                is_broad = False  # Research keywords are trusted
            
            if not is_broad:
                filtered.append(kw)
        
        return filtered

    async def _deduplicate_semantic(self, keywords: list[dict]) -> list[dict]:
        """
        AI semantic deduplication using a single Gemini prompt.
        Removes near-duplicates like "sign up X" vs "sign up for X".
        Keeps the highest-scored keyword from each group.
        """
        if not keywords or len(keywords) < 2:
            return keywords

        # Sort by score descending (best first)
        sorted_kws = sorted(keywords, key=lambda x: x.get("score", 0), reverse=True)

        # Build simple list for the prompt
        keyword_list = "\n".join(kw.get("keyword", "") for kw in sorted_kws)

        prompt = f"""You have {len(sorted_kws)} keywords sorted by quality (best first).
Remove DUPLICATES - keep only the first (best) one from each group of similar keywords.

WHAT ARE DUPLICATES (remove the later one):
- "sign up X" vs "sign up for X" → keep first
- "review" vs "reviews" → keep first
- "job search" vs "job hunting" vs "job searching" → keep first
- "how to find X" vs "how find X" → keep first
- Same words different order → keep first

WHAT ARE NOT DUPLICATES (keep both):
- Different locations: "jobs berlin" vs "jobs munich"
- Different topics: "tech jobs" vs "startup jobs"
- Different intents: "buy X" vs "what is X"

Keywords (best quality first):
{keyword_list}

Return JSON with ONLY the unique keywords to keep:
{{"keep": ["keyword1", "keyword2", "keyword3", ...]}}"""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )

            data = self._parse_json_response(response.text)
            keep_list = data.get("keep", [])

            if not keep_list:
                logger.warning("AI dedup returned empty list, keeping original")
                return keywords

            # Build lookup set (case-insensitive, normalized)
            keep_normalized = set()
            for k in keep_list:
                normalized = " ".join(str(k).lower().split())
                keep_normalized.add(normalized)

            # Filter to keep only keywords in the list
            kept = []
            for kw in sorted_kws:
                kw_normalized = " ".join(kw.get("keyword", "").lower().split())
                if kw_normalized in keep_normalized:
                    kept.append(kw)
                    keep_normalized.discard(kw_normalized)  # Avoid re-adding

            removed = len(keywords) - len(kept)
            if removed > 0:
                logger.info(f"AI semantic dedup: removed {removed} near-duplicates")

            return kept

        except Exception as e:
            logger.error(f"AI semantic dedup failed: {e}")
            return keywords

    async def _score_keywords(
        self, keywords: list[dict], company_info: CompanyInfo
    ) -> list[dict]:
        """Score keywords for company fit using Gemini."""
        if not keywords:
            return []

        # Score ALL keywords for company-fit, including gap keywords
        # Gap keywords have aeo_score from SE Ranking, but we need company-fit score
        # This ensures all keywords are scored consistently for company relevance
        
        if not keywords:
            return keywords
        
        # Score all keywords (including gap keywords) for company-fit
        keywords_to_score = keywords

        # Build company context
        context_parts = [f"Company: {company_info.name}"]
        if company_info.description:
            context_parts.append(f"Description: {company_info.description}")
        if company_info.services:
            context_parts.append(f"Services: {', '.join(company_info.services)}")
        if company_info.products:
            context_parts.append(f"Products: {', '.join(company_info.products)}")
        if company_info.industry:
            context_parts.append(f"Industry: {company_info.industry}")

        company_context = "\n".join(context_parts)

        # Score ALL keywords (including gap keywords) for company-fit
        # Score in batches
        batch_size = 25
        num_batches = (len(keywords_to_score) + batch_size - 1) // batch_size

        tasks = [
            self._score_batch(
                keywords_to_score[i * batch_size : (i + 1) * batch_size],
                company_context,
                i + 1,
                num_batches,
            )
            for i in range(num_batches)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scored_keywords = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Scoring batch {i + 1} failed: {result}")
                # Keep keywords with default score (or preserve existing score for gap keywords)
                batch = keywords_to_score[i * batch_size : (i + 1) * batch_size]
                for kw in batch:
                    # Preserve aeo_score for gap keywords if scoring fails
                    if kw.get("source") == "gap_analysis" and "aeo_score" in kw:
                        kw["score"] = kw.get("score", kw.get("aeo_score", 50))
                    else:
                        kw["score"] = kw.get("score", 50)
                scored_keywords.extend(batch)
            elif result:
                scored_keywords.extend(result)

        # Sort by score (company-fit score, not aeo_score)
        scored_keywords.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored_keywords

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _score_batch(
        self,
        keywords: list[dict],
        company_context: str,
        batch_num: int,
        total_batches: int,
    ) -> list[dict]:
        """Score a batch of keywords."""
        keywords_text = "\n".join([f"- {kw['keyword']}" for kw in keywords])

        prompt = f"""Score these keywords for company fit on a 1-100 scale.

{company_context}

Keywords to score:
{keywords_text}

Scoring criteria:
- Product/Service relevance (0-40 points)
- Search intent match (0-30 points)
- Business value potential (0-30 points)

Return ONLY a JSON object:
{{"scores": [{{"keyword": "exact keyword", "score": 75}}]}}"""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )

            data = self._parse_json_response(response.text)
            scores_data = data.get("scores", [])

            if isinstance(scores_data, list):
                score_map = {item["keyword"]: item.get("score", 50) for item in scores_data}

                scored = []
                for kw in keywords:
                    kw_copy = dict(kw)
                    kw_copy["score"] = score_map.get(kw["keyword"], 50)
                    scored.append(kw_copy)

                logger.info(f"Scoring batch {batch_num}/{total_batches}: {len(scored)} keywords")
                return scored

        except Exception as e:
            logger.error(f"Scoring batch {batch_num} failed: {e}")
            raise

        return keywords

    async def _generate_content_brief(
        self,
        keyword: str,
        research_data: Optional[dict],
        serp_data: Optional[dict],
        company_info: CompanyInfo,
    ) -> Optional[dict]:
        """
        Generate content briefing for a keyword.
        
        Creates content_angle, target_questions, audience_pain_point, etc.
        """
        if not self.api_key:
            return None
        
        try:
            # Collect sources for attribution
            sources = []
            
            # Build context from research and SERP
            research_context = ""
            if research_data and research_data.get("sources"):
                top_quotes = []
                for source in research_data["sources"][:5]:  # Top 5 for attribution
                    quote = source.get("quote", "")
                    if quote:
                        platform = source.get("platform", "source")
                        top_quotes.append(f"{platform}: '{quote[:150]}...'")
                        
                        # Add research source
                        sources.append({
                            "type": "research",
                            "platform": platform,
                            "url": source.get("url"),
                            "title": source.get("source_title"),
                            "quote": quote[:200] if quote else None,
                        })
                if top_quotes:
                    research_context = "Research findings:\n" + "\n".join(top_quotes)
            
            serp_context = ""
            if serp_data:
                content_types = serp_data.get("common_content_types", [])
                gaps = serp_data.get("content_gaps_identified", [])
                avg_wc = serp_data.get("avg_word_count", 0)
                serp_context = f"""
SERP Analysis:
- Average word count: {avg_wc}
- Common content types: {', '.join(content_types[:3])}
- Content gaps: {', '.join(gaps[:3]) if gaps else 'None identified'}
"""
                
                # Add top SERP sources
                organic_results = serp_data.get("organic_results", [])
                for result in organic_results[:3]:  # Top 3 ranking pages
                    if isinstance(result, dict):
                        sources.append({
                            "type": "serp",
                            "url": result.get("url"),
                            "title": result.get("title"),
                            "position": result.get("position"),
                        })
                
                # Add PAA sources
                paa_questions = serp_data.get("paa_questions", [])
                for paa in paa_questions[:3]:  # Top 3 PAA questions
                    if isinstance(paa, dict):
                        sources.append({
                            "type": "paa",
                            "title": paa.get("question"),
                            "url": paa.get("source_url"),
                        })
            
            # Build company context
            company_context_parts = [f"Company: {company_info.name}"]
            if company_info.description:
                company_context_parts.append(f"Description: {company_info.description[:200]}")
            if company_info.services:
                company_context_parts.append(f"Services: {', '.join(company_info.services[:3])}")
            if company_info.products:
                company_context_parts.append(f"Products: {', '.join(company_info.products[:3])}")
            company_context = "\n".join(company_context_parts)
            
            # Build sources list for prompt context
            sources_context = ""
            if sources:
                sources_list = []
                for i, src in enumerate(sources[:8], 1):  # Top 8 sources
                    src_desc = f"{i}. {src.get('type', 'source').upper()}"
                    if src.get('platform'):
                        src_desc += f" ({src['platform']})"
                    if src.get('title'):
                        src_desc += f": {src['title'][:100]}"
                    if src.get('url'):
                        src_desc += f" - {src['url']}"
                    sources_list.append(src_desc)
                sources_context = "\n\nSources available:\n" + "\n".join(sources_list)
            
            prompt = f"""Generate a content briefing for this keyword: "{keyword}"

{company_context}

{research_context}

{serp_context}
{sources_context}

Create a comprehensive content brief that includes:

1. Content Angle: What approach/angle should the article take? (1-2 sentences)
2. Target Questions: List 5-7 specific questions the article should answer (from PAA + research)
3. Content Gap: What's missing in current SERP content? (1-2 sentences)
4. Audience Pain Point: Summarize what users are looking for - "Users were looking for X" (1-2 sentences)
5. Recommended Word Count: Based on SERP analysis (number)
6. Featured Snippet Opportunity: What type of featured snippet opportunity exists? (paragraph, list, table, none)
7. Research Context: Summary of user needs from research (2-3 sentences)

IMPORTANT: Reference specific sources when making claims. For example:
- "Based on Reddit discussions, users were looking for..."
- "According to top-ranking SERP results, the content gap is..."
- "PAA questions indicate users want to know..."

Return JSON:
{{
  "content_angle": "...",
  "target_questions": ["question1", "question2", ...],
  "content_gap": "...",
  "audience_pain_point": "Users were looking for...",
  "recommended_word_count": 1800,
  "fs_opportunity_type": "paragraph|list|table|none",
  "research_context": "..."
}}"""
            
            # Use new SDK for consistency (same as ResearchEngine and GeminiSerpAnalyzer)
            from google import genai as genai_new
            
            client = genai_new.Client(api_key=self.api_key)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=genai_new.types.GenerateContentConfig(
                    temperature=0.5,
                    response_mime_type="application/json",
                ),
            )
            
            # Parse response with error handling
            if not hasattr(response, 'text') or not response.text:
                logger.warning(f"Empty response for content brief '{keyword}'")
                return None
            
            try:
                data = self._parse_json_response(response.text)
                # Validate required fields
                if not isinstance(data, dict) or not data.get("content_angle") or not data.get("target_questions"):
                    logger.warning(f"Incomplete content brief for '{keyword}' - missing required fields")
                    return None
                
                # Add sources to the brief
                data["sources"] = sources
                
                return data
            except (KeyError, AttributeError, TypeError) as e:
                logger.error(f"Failed to parse content brief JSON for '{keyword}': {e}")
                return None
            
        except Exception as e:
            logger.error(f"Content briefing generation failed for '{keyword}': {e}")
            return None
    
    async def _cluster_keywords(
        self, keywords: list[dict], company_info: CompanyInfo, cluster_count: int
    ) -> list[dict]:
        """Cluster keywords into semantic groups using Gemini."""
        if not keywords:
            return []

        keywords_text = "\n".join([f"- {kw['keyword']}" for kw in keywords])

        prompt = f"""Group these keywords into {cluster_count} semantic clusters for {company_info.name}.

Keywords:
{keywords_text}

Requirements:
- Create exactly {cluster_count} clusters
- Each cluster should have a descriptive name (2-4 words)
- Group keywords by theme/topic
- Each keyword should belong to exactly one cluster

Return ONLY a JSON object:
{{"clusters": [
  {{"cluster_name": "Product Features", "keywords": ["keyword1", "keyword2"]}},
  {{"cluster_name": "How-To Guides", "keywords": ["keyword3", "keyword4"]}}
]}}"""

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.5,
                    response_mime_type="application/json",
                ),
            )

            data = self._parse_json_response(response.text)
            clusters_data = data.get("clusters", [])

            if isinstance(clusters_data, list):
                # Map cluster names to keywords
                cluster_map = {}
                for cluster in clusters_data:
                    cluster_name = cluster.get("cluster_name", "Uncategorized")
                    for kw_text in cluster.get("keywords", []):
                        cluster_map[kw_text.lower().strip()] = cluster_name

                # Apply cluster names
                for kw in keywords:
                    kw_text = kw["keyword"].lower().strip()
                    kw["cluster_name"] = cluster_map.get(kw_text, "Other")

                logger.info(
                    f"Clustered {len(keywords)} keywords into {len(clusters_data)} groups"
                )

        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            for kw in keywords:
                kw["cluster_name"] = "General"

        return keywords

    def _parse_json_response(self, response_text: str) -> dict:
        """Parse JSON from AI response, handling markdown code blocks."""
        try:
            text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            return json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"JSON parse error: {e}. Response: {response_text[:200]}")
            return {"keywords": []}

    async def _get_autocomplete_keywords(
        self,
        company_info: CompanyInfo,
        config: GenerationConfig,
    ) -> list[dict]:
        """
        Get keyword suggestions from Google Autocomplete (FREE).
        
        Uses company name, products, and services as seed keywords.
        Returns question keywords and long-tail variations.
        """
        from .autocomplete_analyzer import GoogleAutocompleteAnalyzer
        
        analyzer = GoogleAutocompleteAnalyzer(
            country=config.region,
            language=config.language.split()[0].lower(),  # "english" -> "en"
            max_concurrent=5,
        )
        
        # Generate seed keywords from company info
        seed_keywords = []
        if company_info.name:
            seed_keywords.append(company_info.name.lower())
        if company_info.products:
            seed_keywords.extend([p.lower() for p in company_info.products[:3]])
        if company_info.services:
            seed_keywords.extend([s.lower() for s in company_info.services[:3]])
        
        # Limit to first 5 seeds to avoid rate limits
        seed_keywords = list(set(seed_keywords))[:5]
        
        if not seed_keywords:
            logger.warning("No seed keywords for autocomplete - skipping")
            return []
        
        # Get autocomplete suggestions for each seed
        all_suggestions = []
        for seed in seed_keywords:
            try:
                result = await analyzer.get_suggestions(seed, include_questions=True)
                if result.question_keywords:
                    all_suggestions.extend(result.question_keywords[:15])
                if result.long_tail_keywords:
                    all_suggestions.extend(result.long_tail_keywords[:15])
            except Exception as e:
                logger.warning(f"Autocomplete failed for '{seed}': {e}")
                continue
        
        # Deduplicate and limit
        unique_suggestions = list(set(all_suggestions))[:config.autocomplete_expansion_limit]
        
        # Convert to keyword format
        keyword_dicts = [
            {
                "keyword": kw,
                "intent": "question" if "?" in kw or any(q in kw.lower() for q in ["how", "what", "why", "when", "where", "who"]) else "informational",
                "score": 0,  # Will be scored later
                "source": "autocomplete",
                "is_question": "?" in kw or any(q in kw.lower() for q in ["how", "what", "why", "when", "where", "who"]),
            }
            for kw in unique_suggestions
        ]
        
        return keyword_dicts
    
    async def _enrich_with_trends(
        self,
        keywords: list[str],
        config: GenerationConfig,
    ) -> dict[str, "GoogleTrendsData"]:
        """
        Enrich keywords with Google Trends data (FREE).
        
        Returns mapping of keyword -> GoogleTrendsData.
        Limited to top keywords due to rate limits.
        """
        from .google_trends_analyzer import GoogleTrendsAnalyzer
        from .models import GoogleTrendsData
        
        analyzer = GoogleTrendsAnalyzer(
            country=config.region.upper(),
            language=config.language.split()[0].lower(),
            timeframe="today 12-m",
            max_concurrent=3,  # Be gentle with Google
        )
        
        trends_map = {}
        
        # Process in batches of 5 (pytrends limitation)
        batch_size = 5
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i+batch_size]
            
            try:
                trend_data = await analyzer.analyze_keywords(batch)
                
                for kw, data in trend_data.items():
                    if data.error:
                        logger.debug(f"Trends error for '{kw}': {data.error}")
                        continue
                    
                    # Convert to GoogleTrendsData model
                    trends_map[kw] = GoogleTrendsData(
                        keyword=kw,
                        current_interest=data.current_interest,
                        avg_interest=data.avg_interest,
                        peak_interest=data.peak_interest,
                        trend_direction=data.trend_direction,
                        trend_percentage=data.trend_percentage,
                        is_seasonal=data.is_seasonal,
                        peak_months=data.peak_months,
                        rising_related=[r.get("query", r) if isinstance(r, dict) else r for r in data.rising_related[:10]],
                        top_related=[r.get("query", r) if isinstance(r, dict) else r for r in data.top_related[:10]],
                        top_regions=[{"region": r.get("geoName", ""), "value": r.get("value", 0)} for r in data.top_regions[:5]] if data.top_regions else [],
                    )
                
                # Add small delay between batches to avoid rate limits
                if i + batch_size < len(keywords):
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.warning(f"Trends batch {i//batch_size + 1} failed: {e}")
                continue
        
        return trends_map

    def _calculate_statistics(
        self, keywords: list[Keyword], duplicate_count: int
    ) -> KeywordStatistics:
        """Calculate statistics for generated keywords."""
        if not keywords:
            return KeywordStatistics(total=0, duplicate_count=duplicate_count)

        intent_counts = defaultdict(int)
        length_counts = {"short": 0, "medium": 0, "long": 0}
        source_counts = defaultdict(int)

        for kw in keywords:
            intent_counts[kw.intent] += 1
            source_counts[kw.source] += 1

            word_count = len(kw.keyword.split())
            if word_count <= 3:
                length_counts["short"] += 1
            elif word_count <= 5:
                length_counts["medium"] += 1
            else:
                length_counts["long"] += 1

        return KeywordStatistics(
            total=len(keywords),
            avg_score=sum(kw.score for kw in keywords) / len(keywords),
            intent_breakdown=dict(intent_counts),
            word_length_distribution=length_counts,
            source_breakdown=dict(source_counts),
            duplicate_count=duplicate_count,
        )
