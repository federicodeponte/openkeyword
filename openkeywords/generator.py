"""
Core keyword generation using Google Gemini + SE Ranking gap analysis
"""

import asyncio
import json
import logging
import os
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

# Valid intent types
VALID_INTENTS = {"transactional", "commercial", "comparison", "informational", "question"}


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
        model: str = "gemini-1.5-flash",
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

        all_keywords = []

        # Step 1: SE Ranking gap analysis (if available and company has URL)
        gap_keywords = []
        if self.seranking_client and company_info.url:
            gap_keywords = await self._get_gap_keywords(company_info, config)
            logger.info(f"Got {len(gap_keywords)} gap keywords from SE Ranking")
            all_keywords.extend(gap_keywords)

        # Step 2: AI keyword generation
        # Generate more AI keywords if we didn't get enough from gap analysis
        ai_target = max(config.target_count - len(gap_keywords), config.target_count // 2)
        ai_keywords = await self._generate_ai_keywords(company_info, config, ai_target)
        logger.info(f"Generated {len(ai_keywords)} AI keywords")
        all_keywords.extend(ai_keywords)

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

        # Step 4: Score keywords
        all_keywords = await self._score_keywords(all_keywords, company_info)
        logger.info(f"Scored {len(all_keywords)} keywords")

        # Step 5: AI semantic deduplication (removes "sign up X" vs "sign up for X" etc.)
        all_keywords = await self._deduplicate_semantic(all_keywords)
        logger.info(f"After AI semantic dedup: {len(all_keywords)} keywords")

        # Step 6: Filter by score
        all_keywords = [kw for kw in all_keywords if kw.get("score", 0) >= config.min_score]
        logger.info(f"After score filter: {len(all_keywords)} keywords")

        # Step 7: Cluster keywords
        if config.enable_clustering and len(all_keywords) > 0:
            all_keywords = await self._cluster_keywords(
                all_keywords, company_info, config.cluster_count
            )

        # Step 8: Limit to target count
        all_keywords = all_keywords[: config.target_count]

        # Build result
        keyword_objects = [
            Keyword(
                keyword=kw["keyword"],
                intent=kw.get("intent", "informational"),
                score=kw.get("score", 0),
                cluster_name=kw.get("cluster_name"),
                is_question=kw.get("is_question", False),
                volume=kw.get("volume", 0),
                difficulty=kw.get("difficulty", 50),
            )
            for kw in all_keywords
        ]

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

        # Dynamic language handling - no hardcoded lists
        prompt = f"""Generate {batch_count} SEO keywords in {language.upper()} language for the {region.upper()} market.

{company_context}

INTENT TYPES (strict counts):
- {question_min}+ QUESTION: keywords that start with question words in {language} (how, what, why, when, where, which, who, can, should, etc.)
- {transactional_min}+ TRANSACTIONAL: keywords with buying/action intent (book, buy, order, get quote, sign up, etc.)
- {comparison_min}+ COMPARISON: keywords comparing options (vs, versus, alternative, difference, compared to, etc.)
- {commercial_min}+ COMMERCIAL: keywords with commercial intent (best, top, review, pricing, cost, etc.)
- Rest INFORMATIONAL (max 25%): guides, benefits, tips

KEYWORD LENGTH:
- 20% SHORT keywords (2-3 words)
- 50% MEDIUM keywords (4-5 words)
- 30% LONG keywords (6-7 words)

RULES:
- ALL keywords must be in {language.upper()} language
- NO single-word keywords
- NO keywords longer than 7 words
- Be specific to company offerings
- Include location terms relevant to {region.upper()} market

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

        # Keywords from gap analysis already have scores (aeo_score)
        # Only score AI-generated keywords
        ai_keywords = [kw for kw in keywords if kw.get("source") != "gap_analysis"]
        gap_keywords = [kw for kw in keywords if kw.get("source") == "gap_analysis"]

        if not ai_keywords:
            return keywords

        # Build company context
        context_parts = [f"Company: {company_info.name}"]
        if company_info.description:
            context_parts.append(f"Description: {company_info.description}")
        if company_info.services:
            context_parts.append(f"Services: {', '.join(company_info.services)}")
        if company_info.products:
            context_parts.append(f"Products: {', '.join(company_info.products)}")

        company_context = "\n".join(context_parts)

        # Score in batches
        batch_size = 25
        num_batches = (len(ai_keywords) + batch_size - 1) // batch_size

        tasks = [
            self._score_batch(
                ai_keywords[i * batch_size : (i + 1) * batch_size],
                company_context,
                i + 1,
                num_batches,
            )
            for i in range(num_batches)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scored_ai = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Scoring batch {i + 1} failed: {result}")
                # Keep keywords with default score
                batch = ai_keywords[i * batch_size : (i + 1) * batch_size]
                for kw in batch:
                    kw["score"] = 50
                scored_ai.extend(batch)
            elif result:
                scored_ai.extend(result)

        # Combine and sort by score
        all_scored = gap_keywords + scored_ai
        all_scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_scored

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

    def _calculate_statistics(
        self, keywords: list[Keyword], duplicate_count: int
    ) -> KeywordStatistics:
        """Calculate statistics for generated keywords."""
        if not keywords:
            return KeywordStatistics(total=0, duplicate_count=duplicate_count)

        intent_counts = defaultdict(int)
        length_counts = {"short": 0, "medium": 0, "long": 0}

        for kw in keywords:
            intent_counts[kw.intent] += 1

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
            duplicate_count=duplicate_count,
        )
