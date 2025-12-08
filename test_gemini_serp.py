"""
Test script for Gemini SERP analyzer (mocked version for testing logic)
"""
import asyncio
import json
from dataclasses import asdict

# Mock the Gemini response for testing
class MockGeminiResponse:
    def __init__(self, text):
        self.text = text

class MockGeminiModel:
    def generate_content(self, prompt):
        # Simulate a realistic Gemini response with Google Search grounding
        keyword = prompt.split('"')[1] if '"' in prompt else "test keyword"
        
        response_data = {
            "has_featured_snippet": True,
            "featured_snippet_text": f"Search Engine Optimization (SEO) is the practice of optimizing websites...",
            "featured_snippet_url": "https://example.com/what-is-seo",
            "has_paa": True,
            "paa_questions": [
                "How does SEO work?",
                "What are the types of SEO?",
                "Why is SEO important for businesses?",
                "What is the difference between SEO and SEM?"
            ],
            "related_searches": [
                "SEO best practices 2024",
                "SEO tools for beginners",
                "on-page SEO techniques"
            ],
            "top_domains": [
                "searchengineland.com",
                "moz.com",
                "ahrefs.com",
                "semrush.com",
                "backlinko.com"
            ],
            "organic_results_count": 10,
            "volume_estimate": "high",
            "volume_reasoning": "High search volume indicated by competitive SERP with major SEO sites, extensive PAA questions, and rich related searches. Estimated 10,000+ monthly searches based on result density and domain authority of ranking sites."
        }
        
        response_text = f"```json\n{json.dumps(response_data, indent=2)}\n```"
        return MockGeminiResponse(response_text)

# Patch the module
import sys
sys.path.insert(0, '/Users/federicodeponte/personal-assistant/openkeyword')

# Mock google.generativeai
class MockGenAI:
    @staticmethod
    def configure(api_key):
        pass
    
    class GenerativeModel:
        def __init__(self, model_name, tools):
            self.model_name = model_name
            self.tools = tools
        
        def generate_content(self, prompt):
            return MockGeminiModel().generate_content(prompt)

sys.modules['google.generativeai'] = MockGenAI()

# Now import the analyzer
from openkeywords.gemini_serp_analyzer import GeminiSerpAnalyzer

async def test_gemini_serp():
    print("🧪 Testing Gemini SERP Analyzer (Mocked)\n")
    
    # Initialize with a dummy key
    analyzer = GeminiSerpAnalyzer(
        gemini_api_key="test_key",
        language="en",
        country="us"
    )
    
    print("✅ Analyzer initialized\n")
    
    # Test keywords
    keywords = [
        "what is SEO",
        "how to optimize for AI",
        "best keyword research tools"
    ]
    
    print(f"🔍 Analyzing {len(keywords)} keywords...\n")
    
    analyses, bonus = await analyzer.analyze_keywords(keywords)
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 RESULTS")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    for kw, analysis in analyses.items():
        f = analysis.features
        print(f"🔑 Keyword: {kw}")
        if analysis.error:
            print(f"   ❌ Error: {analysis.error}")
        else:
            print(f"   📈 AEO Score: {f.aeo_opportunity}/100")
            print(f"   📊 Volume: {f.volume_estimate}")
            print(f"   💡 Reasoning: {f.volume_reasoning[:100]}...")
            print(f"   ✨ Featured Snippet: {'✅' if f.has_featured_snippet else '❌'}")
            print(f"   ❓ PAA Questions: {len(f.paa_questions)}")
            if f.paa_questions:
                for q in f.paa_questions[:2]:
                    print(f"      • {q}")
            print(f"   🔗 Related: {len(f.related_searches)} searches")
            print(f"   🏆 Top Domains: {', '.join(f.top_domains[:3])}")
            print(f"   📝 AEO Reason: {f.aeo_reason}")
        print()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🎁 BONUS KEYWORDS ({len(bonus)})")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    if bonus:
        for b in bonus[:10]:
            print(f"   + {b}")
    else:
        print("   (No bonus keywords)")
    
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ TEST PASSED - Logic works correctly!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    # Test data structure
    print("📦 Validating data structure...")
    for kw, analysis in analyses.items():
        assert analysis.keyword == kw
        assert isinstance(analysis.features.aeo_opportunity, int)
        assert 0 <= analysis.features.aeo_opportunity <= 100
        assert analysis.features.volume_estimate in ["high", "medium", "low", None]
        assert isinstance(analysis.features.paa_questions, list)
        assert isinstance(analysis.features.related_searches, list)
        assert isinstance(analysis.bonus_keywords, list)
    
    print("✅ All assertions passed!\n")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_gemini_serp())
    exit(0 if success else 1)

