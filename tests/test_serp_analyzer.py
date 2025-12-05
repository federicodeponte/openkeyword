"""Tests for SERP analyzer module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from openkeywords.serp_analyzer import (
    SerpAnalyzer,
    SerpFeatures,
    SerpAnalysis,
    analyze_for_aeo,
)


class TestSerpFeatures:
    """Tests for SerpFeatures dataclass."""

    def test_defaults(self):
        """Test default values."""
        features = SerpFeatures()
        assert features.has_featured_snippet is False
        assert features.has_paa is False
        assert features.paa_questions == []
        assert features.related_searches == []
        assert features.aeo_opportunity == 0

    def test_with_values(self):
        """Test with custom values."""
        features = SerpFeatures(
            has_featured_snippet=True,
            featured_snippet_text="Example snippet",
            has_paa=True,
            paa_questions=["What is X?", "How to Y?"],
            aeo_opportunity=85,
            aeo_reason="Has featured snippet",
        )
        assert features.has_featured_snippet is True
        assert features.featured_snippet_text == "Example snippet"
        assert len(features.paa_questions) == 2
        assert features.aeo_opportunity == 85


class TestSerpAnalysis:
    """Tests for SerpAnalysis dataclass."""

    def test_defaults(self):
        """Test default values."""
        analysis = SerpAnalysis(keyword="test", features=SerpFeatures())
        assert analysis.keyword == "test"
        assert analysis.error is None
        assert analysis.bonus_keywords == []

    def test_with_bonus_keywords(self):
        """Test with bonus keywords."""
        analysis = SerpAnalysis(
            keyword="test",
            features=SerpFeatures(),
            bonus_keywords=["related1", "related2"],
        )
        assert len(analysis.bonus_keywords) == 2


class TestSerpAnalyzerInit:
    """Tests for SerpAnalyzer initialization."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        analyzer = SerpAnalyzer()
        assert analyzer.language == "en"
        assert analyzer.country == "us"
        assert analyzer.max_concurrent == 5
        # Not configured without credentials
        assert analyzer.is_configured() is False

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        analyzer = SerpAnalyzer(
            dataforseo_login="test@example.com",
            dataforseo_password="test123",
            language="de",
            country="de",
            max_concurrent=3,
        )
        assert analyzer.language == "de"
        assert analyzer.country == "de"
        assert analyzer.max_concurrent == 3
        assert analyzer.is_configured() is True


class TestAEOOpportunityCalculation:
    """Tests for AEO opportunity score calculation."""

    def test_base_score(self):
        """Test base score for features with big players (no boosts)."""
        analyzer = SerpAnalyzer()
        # Add big players to avoid "no major sites" boost
        features = SerpFeatures(top_domains=["wikipedia.org", "amazon.com", "youtube.com"])
        score, reason = analyzer._calculate_aeo_opportunity("test keyword", features)
        assert score == 35  # Base 50 - 15 high competition
        assert "High competition" in reason

    def test_featured_snippet_boost(self):
        """Test score boost for featured snippet."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures(has_featured_snippet=True)
        score, reason = analyzer._calculate_aeo_opportunity("test keyword", features)
        assert score >= 75  # 50 base + 25 featured snippet
        assert "featured snippet" in reason.lower()

    def test_paa_boost(self):
        """Test score boost for PAA."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures(has_paa=True, paa_questions=["Q1", "Q2", "Q3", "Q4"])
        score, reason = analyzer._calculate_aeo_opportunity("test keyword", features)
        assert score >= 70  # 50 + 15 + 5 for rich PAA
        assert "PAA" in reason

    def test_question_keyword_boost(self):
        """Test score boost for question keywords."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures()
        score, reason = analyzer._calculate_aeo_opportunity("how to optimize SEO", features)
        assert score >= 60  # 50 + 10 for question
        assert "Question" in reason

    def test_no_big_players_boost(self):
        """Test score boost when no big players in top 5."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures(top_domains=["smallsite.com", "another.com"])
        score, reason = analyzer._calculate_aeo_opportunity("niche keyword", features)
        assert score >= 60  # 50 + 10 for no major sites
        assert "No major sites" in reason

    def test_high_competition_penalty(self):
        """Test score penalty for high competition."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures(top_domains=["wikipedia.org", "amazon.com", "youtube.com", "linkedin.com"])
        score, reason = analyzer._calculate_aeo_opportunity("competitive keyword", features)
        assert score < 50  # 50 - 15 for high competition
        assert "High competition" in reason

    def test_combined_boosts(self):
        """Test combined boosts for ideal keyword."""
        analyzer = SerpAnalyzer()
        features = SerpFeatures(
            has_featured_snippet=True,
            has_paa=True,
            paa_questions=["Q1", "Q2", "Q3", "Q4"],
            top_domains=["smallsite.com"],
        )
        score, reason = analyzer._calculate_aeo_opportunity("what is AEO", features)
        # Should have high score: 50 + 25 (FS) + 15 (PAA) + 5 (rich) + 10 (question) + 10 (no big) = 100+
        assert score >= 95  # Capped at 100


class TestSerpAnalyzerParsing:
    """Tests for SERP response parsing."""

    def test_parse_with_featured_snippet(self):
        """Test parsing response with featured snippet."""
        from openkeywords.dataforseo_client import SerpResponse, SearchResult
        
        analyzer = SerpAnalyzer(dataforseo_login="test", dataforseo_password="test")
        response = SerpResponse(
            success=True,
            query="test keyword",
            results=[],
            featured_snippet={
                "snippet": "This is the answer",
                "link": "https://example.com",
            },
            people_also_ask=[],
            related_searches=[],
        )
        analysis = analyzer._parse_serp_response("test keyword", response)
        assert analysis.features.has_featured_snippet is True
        assert analysis.features.featured_snippet_text == "This is the answer"

    def test_parse_with_paa(self):
        """Test parsing response with PAA."""
        from openkeywords.dataforseo_client import SerpResponse
        
        analyzer = SerpAnalyzer(dataforseo_login="test", dataforseo_password="test")
        response = SerpResponse(
            success=True,
            query="test keyword",
            results=[],
            featured_snippet=None,
            people_also_ask=[
                {"question": "What is SEO?"},
                {"question": "How does SEO work?"},
            ],
            related_searches=[],
        )
        analysis = analyzer._parse_serp_response("test keyword", response)
        assert analysis.features.has_paa is True
        assert len(analysis.features.paa_questions) == 2
        assert "What is SEO?" in analysis.features.paa_questions

    def test_parse_extracts_bonus_keywords(self):
        """Test that PAA and related searches become bonus keywords."""
        from openkeywords.dataforseo_client import SerpResponse
        
        analyzer = SerpAnalyzer(dataforseo_login="test", dataforseo_password="test")
        response = SerpResponse(
            success=True,
            query="test keyword",
            results=[],
            featured_snippet=None,
            people_also_ask=[{"question": "What is X?"}],
            related_searches=[{"query": "related search"}],
        )
        analysis = analyzer._parse_serp_response("test keyword", response)
        assert "What is X?" in analysis.bonus_keywords
        assert "related search" in analysis.bonus_keywords


class TestAnalyzeForAEO:
    """Tests for the convenience function."""

    @pytest.mark.asyncio
    async def test_analyze_for_aeo_empty_keywords(self):
        """Test with empty keyword list."""
        with patch.object(SerpAnalyzer, "analyze_keywords", new_callable=AsyncMock) as mock:
            mock.return_value = ({}, [])
            analyses, bonus = await analyze_for_aeo([])
            # Empty list should still work
            assert analyses == {} or mock.called


class TestSerpAnalyzerAnalyzeKeywords:
    """Tests for keyword analysis."""

    @pytest.mark.asyncio
    async def test_analyze_keywords_success(self):
        """Test successful keyword analysis with mocked DataForSEO client."""
        from openkeywords.dataforseo_client import SerpResponse, SearchResult
        
        analyzer = SerpAnalyzer(dataforseo_login="test", dataforseo_password="test")
        
        # Mock the DataForSEO client's search method
        mock_response = SerpResponse(
            success=True,
            query="test keyword",
            results=[SearchResult(position=1, title="Test", link="https://smallsite.com", snippet="test")],
            featured_snippet={"snippet": "Answer", "link": "https://example.com"},
            people_also_ask=[{"question": "Related question?"}],
            related_searches=[{"query": "related term"}],
        )
        
        with patch.object(analyzer, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            analyses, bonus = await analyzer.analyze_keywords(["test keyword"])
            
            assert "test keyword" in analyses
            assert analyses["test keyword"].features.has_featured_snippet is True
            assert "Related question?" in bonus or "related term" in bonus

    @pytest.mark.asyncio
    async def test_analyze_keywords_removes_original_from_bonus(self):
        """Test that original keywords are not in bonus list."""
        from openkeywords.dataforseo_client import SerpResponse
        
        analyzer = SerpAnalyzer(dataforseo_login="test", dataforseo_password="test")
        
        mock_response = SerpResponse(
            success=True,
            query="test keyword",
            results=[],
            featured_snippet=None,
            people_also_ask=[],
            related_searches=[{"query": "test keyword"}],  # Same as input
        )
        
        with patch.object(analyzer, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            analyses, bonus = await analyzer.analyze_keywords(["test keyword"])
            
            # Original keyword should not be in bonus
            assert "test keyword" not in [b.lower() for b in bonus]
    
    @pytest.mark.asyncio
    async def test_analyze_keywords_not_configured(self):
        """Test behavior when DataForSEO is not configured."""
        analyzer = SerpAnalyzer()  # No credentials
        
        analyses, bonus = await analyzer.analyze_keywords(["test keyword"])
        
        assert "test keyword" in analyses
        assert analyses["test keyword"].error == "DataForSEO not configured"
        assert bonus == []

