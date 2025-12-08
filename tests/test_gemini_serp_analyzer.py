"""
Unit tests for Gemini SERP analyzer
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

from openkeywords.gemini_serp_analyzer import (
    GeminiSerpAnalyzer,
    SerpFeatures,
    SerpAnalysis,
    analyze_for_aeo_gemini,
)


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "has_featured_snippet": True,
        "featured_snippet_text": "SEO is the practice of optimizing websites...",
        "featured_snippet_url": "https://example.com/seo",
        "has_paa": True,
        "paa_questions": [
            "How does SEO work?",
            "What is on-page SEO?",
            "Why is SEO important?"
        ],
        "related_searches": [
            "SEO best practices",
            "SEO tools 2024"
        ],
        "top_domains": [
            "moz.com",
            "ahrefs.com",
            "semrush.com"
        ],
        "organic_results_count": 10,
        "volume_estimate": "high",
        "volume_reasoning": "High competition with major SEO sites ranking"
    }


@pytest.fixture
def analyzer():
    """Create analyzer with test API key."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            return GeminiSerpAnalyzer(
                gemini_api_key="test_key",
                language="en",
                country="us"
            )


def test_init_requires_api_key():
    """Test that initialization requires API key."""
    with pytest.raises(ValueError, match="GEMINI_API_KEY required"):
        GeminiSerpAnalyzer(gemini_api_key=None)


def test_init_with_api_key(analyzer):
    """Test successful initialization with API key."""
    assert analyzer.api_key == "test_key"
    assert analyzer.language == "en"
    assert analyzer.country == "us"
    assert analyzer.is_configured()


def test_parse_gemini_response(analyzer, mock_gemini_response):
    """Test parsing Gemini response into SerpAnalysis."""
    result = analyzer._parse_gemini_response("what is SEO", mock_gemini_response)
    
    assert isinstance(result, SerpAnalysis)
    assert result.keyword == "what is SEO"
    assert result.error is None
    
    f = result.features
    assert f.has_featured_snippet is True
    assert f.featured_snippet_text == "SEO is the practice of optimizing websites..."
    assert f.has_paa is True
    assert len(f.paa_questions) == 3
    assert len(f.related_searches) == 2
    assert len(f.top_domains) == 3
    assert f.volume_estimate == "high"
    assert f.aeo_opportunity > 0


def test_calculate_aeo_opportunity_high_score(analyzer):
    """Test AEO scoring with high-value features."""
    features = SerpFeatures(
        has_featured_snippet=True,
        has_paa=True,
        paa_questions=["q1", "q2", "q3", "q4"],
        top_domains=["niche1.com", "niche2.com"],
        volume_estimate="high"
    )
    
    score, reason = analyzer._calculate_aeo_opportunity("what is SEO", features)
    
    assert score >= 80  # Should be high score
    assert "featured snippet" in reason.lower()
    assert "PAA" in reason or "paa" in reason.lower()
    assert "question keyword" in reason.lower()


def test_calculate_aeo_opportunity_low_score(analyzer):
    """Test AEO scoring with low-value features."""
    features = SerpFeatures(
        has_featured_snippet=False,
        has_paa=False,
        top_domains=["wikipedia.org", "amazon.com", "youtube.com"],  # Big players
        volume_estimate="low"
    )
    
    score, reason = analyzer._calculate_aeo_opportunity("SEO tools", features)
    
    assert score < 60  # Should be lower score
    # High competition should reduce score


def test_bonus_keywords_extraction(analyzer, mock_gemini_response):
    """Test that bonus keywords are extracted from PAA and related."""
    result = analyzer._parse_gemini_response("what is SEO", mock_gemini_response)
    
    assert len(result.bonus_keywords) == 5  # 3 PAA + 2 related
    assert "How does SEO work?" in result.bonus_keywords
    assert "SEO best practices" in result.bonus_keywords


@pytest.mark.asyncio
async def test_analyze_keywords_empty_list(analyzer):
    """Test handling of empty keyword list."""
    analyses, bonus = await analyzer.analyze_keywords([])
    
    assert analyses == {}
    assert bonus == []


@pytest.mark.asyncio
async def test_analyze_keywords_with_mock(analyzer, mock_gemini_response):
    """Test keyword analysis with mocked Gemini response."""
    mock_response = Mock()
    mock_response.text = f"```json\n{json.dumps(mock_gemini_response)}\n```"
    
    with patch.object(analyzer._model, 'generate_content', return_value=mock_response):
        analyses, bonus = await analyzer.analyze_keywords(["what is SEO"])
    
    assert len(analyses) == 1
    assert "what is SEO" in analyses
    assert len(bonus) > 0
    
    analysis = analyses["what is SEO"]
    assert analysis.features.has_featured_snippet is True
    assert analysis.features.volume_estimate == "high"


@pytest.mark.asyncio
async def test_analyze_keywords_filters_original_from_bonus(analyzer, mock_gemini_response):
    """Test that original keywords are filtered from bonus list."""
    mock_response = Mock()
    
    # Add original keyword to PAA questions
    response_data = mock_gemini_response.copy()
    response_data["paa_questions"] = ["what is seo", "how does seo work"]
    mock_response.text = f"```json\n{json.dumps(response_data)}\n```"
    
    with patch.object(analyzer._model, 'generate_content', return_value=mock_response):
        analyses, bonus = await analyzer.analyze_keywords(["what is SEO"])
    
    # Original keyword should be filtered out (case-insensitive)
    assert "what is SEO" not in bonus
    assert "what is seo" not in bonus
    assert "how does seo work" in bonus


@pytest.mark.asyncio
async def test_analyze_keywords_handles_errors(analyzer):
    """Test error handling in keyword analysis."""
    with patch.object(analyzer._model, 'generate_content', side_effect=Exception("API error")):
        analyses, bonus = await analyzer.analyze_keywords(["test"])
    
    assert len(analyses) == 1
    assert analyses["test"].error == "API error"
    assert analyses["test"].features.aeo_opportunity == 0


def test_volume_estimate_scoring(analyzer):
    """Test that volume estimates affect AEO scoring."""
    # High volume
    f_high = SerpFeatures(volume_estimate="high")
    score_high, _ = analyzer._calculate_aeo_opportunity("test", f_high)
    
    # Low volume
    f_low = SerpFeatures(volume_estimate="low")
    score_low, _ = analyzer._calculate_aeo_opportunity("test", f_low)
    
    # Medium volume
    f_medium = SerpFeatures(volume_estimate="medium")
    score_medium, _ = analyzer._calculate_aeo_opportunity("test", f_medium)
    
    assert score_high > score_medium
    assert score_low < score_high


def test_question_keyword_detection(analyzer):
    """Test that question keywords get bonus points."""
    features = SerpFeatures()
    
    question_keywords = [
        "how to optimize for SEO",
        "what is SEO",
        "why is SEO important",
        "when should I use SEO",
        "where to learn SEO",
        "who invented SEO",
    ]
    
    for kw in question_keywords:
        score, reason = analyzer._calculate_aeo_opportunity(kw, features)
        assert "question keyword" in reason.lower()


@pytest.mark.asyncio
async def test_convenience_function():
    """Test the analyze_for_aeo_gemini convenience function."""
    mock_response = Mock()
    mock_response.text = '{"has_featured_snippet": false, "has_paa": false, "paa_questions": [], "related_searches": [], "top_domains": [], "organic_results_count": 0, "volume_estimate": "low", "volume_reasoning": "test"}'
    
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = Mock()
            mock_model.generate_content = Mock(return_value=mock_response)
            mock_model_class.return_value = mock_model
            
            analyses, bonus = await analyze_for_aeo_gemini(
                ["test"],
                gemini_api_key="test_key"
            )
    
    assert len(analyses) == 1
    assert "test" in analyses

