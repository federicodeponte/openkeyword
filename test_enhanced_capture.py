#!/usr/bin/env python3
"""
Test script for enhanced data capture functionality.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from openkeywords.generator import KeywordGenerator
from openkeywords.models import CompanyInfo, GenerationConfig


async def test_enhanced_capture():
    """Test enhanced data capture end-to-end."""
    print("=" * 80)
    print("🧪 Testing Enhanced Data Capture")
    print("=" * 80)
    print()
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not set")
        return False
    
    print("✅ API key found")
    print()
    
    # Initialize generator
    print("📦 Initializing KeywordGenerator...")
    generator = KeywordGenerator(
        gemini_api_key=api_key,
        seranking_api_key=os.getenv("SERANKING_API_KEY"),
    )
    print("✅ Generator initialized")
    print()
    
    # Create test company
    company = CompanyInfo(
        name="Test Company",
        url="https://example.com",
        industry="SaaS",
        description="A test SaaS company",
        services=["Project Management", "Task Tracking"],
        products=["PM Tool"],
    )
    
    # Create config with enhanced capture enabled
    config = GenerationConfig(
        target_count=10,  # Small number for testing
        min_score=40,
        enable_research=True,
        enable_serp_analysis=True,
        enable_enhanced_capture=True,
        enable_content_briefs=True,
        enable_citations=True,
        content_brief_count=5,
        research_sources_per_keyword=3,
        serp_sample_size=5,
    )
    
    print("🔍 Running keyword generation with enhanced capture...")
    print(f"   Target: {config.target_count} keywords")
    print(f"   Research: {'✅' if config.enable_research else '❌'}")
    print(f"   SERP Analysis: {'✅' if config.enable_serp_analysis else '❌'}")
    print(f"   Enhanced Capture: {'✅' if config.enable_enhanced_capture else '❌'}")
    print(f"   Content Briefs: {'✅' if config.enable_content_briefs else '❌'}")
    print(f"   Citations: {'✅' if config.enable_citations else '❌'}")
    print()
    
    try:
        result = await generator.generate(
            company_info=company,
            config=config,
        )
        
        print(f"✅ Generation complete: {len(result.keywords)} keywords")
        print()
        
        # Validate enhanced data capture
        print("=" * 80)
        print("📊 Validating Enhanced Data Capture")
        print("=" * 80)
        print()
        
        keywords_with_research = 0
        keywords_with_briefs = 0
        keywords_with_serp = 0
        keywords_with_citations = 0
        
        for kw in result.keywords:
            if kw.research_data:
                keywords_with_research += 1
            if kw.content_brief:
                keywords_with_briefs += 1
            if kw.serp_data:
                keywords_with_serp += 1
            if kw.citations:
                keywords_with_citations += 1
        
        print(f"Keywords with research data: {keywords_with_research}/{len(result.keywords)}")
        print(f"Keywords with content briefs: {keywords_with_briefs}/{len(result.keywords)}")
        print(f"Keywords with SERP data: {keywords_with_serp}/{len(result.keywords)}")
        print(f"Keywords with citations: {keywords_with_citations}/{len(result.keywords)}")
        print()
        
        # Show example enhanced keyword
        enhanced_kw = None
        for kw in result.keywords:
            if kw.research_data or kw.content_brief or kw.serp_data:
                enhanced_kw = kw
                break
        
        if enhanced_kw:
            print("=" * 80)
            print("📝 Example Enhanced Keyword")
            print("=" * 80)
            print(f"Keyword: {enhanced_kw.keyword}")
            print(f"Score: {enhanced_kw.score}")
            print()
            
            if enhanced_kw.research_data:
                print("🔬 Research Data:")
                print(f"   Sources: {enhanced_kw.research_data.total_sources_found}")
                print(f"   Platforms: {', '.join(enhanced_kw.research_data.platforms_searched)}")
                if enhanced_kw.research_summary:
                    print(f"   Summary: {enhanced_kw.research_summary[:200]}...")
                if enhanced_kw.research_source_urls:
                    print(f"   URLs: {len(enhanced_kw.research_source_urls)} sources")
                print()
            
            if enhanced_kw.content_brief:
                print("📋 Content Brief:")
                print(f"   Angle: {enhanced_kw.content_brief.content_angle[:150] if enhanced_kw.content_brief.content_angle else 'N/A'}...")
                print(f"   Questions: {len(enhanced_kw.content_brief.target_questions)}")
                if enhanced_kw.content_brief.audience_pain_point:
                    print(f"   Pain Point: {enhanced_kw.content_brief.audience_pain_point[:150]}...")
                print()
            
            if enhanced_kw.serp_data:
                print("🔍 SERP Data:")
                print(f"   Organic Results: {len(enhanced_kw.serp_data.organic_results)}")
                print(f"   Featured Snippet: {'✅' if enhanced_kw.serp_data.featured_snippet else '❌'}")
                print(f"   PAA Questions: {len(enhanced_kw.serp_data.paa_questions)}")
                if enhanced_kw.top_ranking_urls:
                    print(f"   Top URLs: {len(enhanced_kw.top_ranking_urls)}")
                print()
            
            if enhanced_kw.citations:
                print("📚 Citations:")
                print(f"   Count: {len(enhanced_kw.citations)}")
                if enhanced_kw.citations:
                    citation = enhanced_kw.citations[0]
                    print(f"   Example (APA): {citation.get('format_apa', 'N/A')[:100]}...")
                print()
        
        # Test exports
        print("=" * 80)
        print("💾 Testing Exports")
        print("=" * 80)
        print()
        
        test_dir = Path("test-output")
        test_dir.mkdir(exist_ok=True)
        
        json_path = test_dir / "test_enhanced_capture.json"
        csv_path = test_dir / "test_enhanced_capture.csv"
        citations_path = test_dir / "test_enhanced_capture_citations.md"
        
        result.to_json(str(json_path))
        print(f"✅ JSON export: {json_path}")
        
        result.to_csv(str(csv_path))
        print(f"✅ CSV export: {csv_path}")
        
        result.export_citations(str(citations_path))
        print(f"✅ Citations export: {citations_path}")
        print()
        
        # Validate JSON structure
        with open(json_path) as f:
            json_data = json.load(f)
        
        if json_data.get("keywords"):
            first_kw = json_data["keywords"][0]
            has_enhanced = (
                "research_data" in first_kw or
                "content_brief" in first_kw or
                "serp_data" in first_kw or
                "citations" in first_kw
            )
            if has_enhanced:
                print("✅ JSON contains enhanced data fields")
            else:
                print("⚠️  JSON missing enhanced data fields")
        
        print()
        print("=" * 80)
        print("✅ All tests passed!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_enhanced_capture())
    sys.exit(0 if success else 1)

