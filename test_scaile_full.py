#!/usr/bin/env python3
"""
Full test for scaile.tech with company analysis first.
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env
env_path = Path(__file__).parent.parent.parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)

from openkeywords.generator import KeywordGenerator
from openkeywords.models import CompanyInfo, GenerationConfig
from openkeywords.company_analyzer import analyze_company


async def test_scaile_full():
    """Test full keyword generation for scaile.tech with company analysis."""
    print("=" * 80)
    print("🧪 FULL TEST: SCAILE.TECH")
    print("=" * 80)
    print()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    print("Step 1: Company Analysis")
    print("-" * 80)
    print("Analyzing scaile.tech...")
    
    try:
        company_analysis = await analyze_company("https://scaile.tech", api_key=api_key)
        print(f"✅ Company analysis complete:")
        print(f"   Name: {company_analysis.get('company_name', 'N/A')}")
        print(f"   Industry: {company_analysis.get('industry', 'N/A')}")
        print(f"   Products: {len(company_analysis.get('products', []))}")
        print(f"   Services: {len(company_analysis.get('services', []))}")
        print(f"   Pain Points: {len(company_analysis.get('pain_points', []))}")
        print()
        
        # Validate analysis quality
        industry = company_analysis.get('industry', '').lower()
        if 'construction' in industry or 'contech' in industry:
            print("⚠️  WARNING: Company analysis may have misread the industry!")
            print("   Detected construction-related industry, but SCAILE is AEO-focused.")
            print("   Continuing anyway - check results carefully.")
            print()
    except Exception as e:
        print(f"⚠️  Company analysis failed: {e}")
        print("   Continuing with fallback company info...")
        company_analysis = {}
    
    # Build CompanyInfo from analysis (with fallbacks)
    # Handle list values (convert to string if needed)
    target_audience = company_analysis.get("target_audience", "B2B SaaS companies")
    if isinstance(target_audience, list):
        target_audience = ", ".join(target_audience)
    
    company = CompanyInfo(
        name=company_analysis.get("company_name", "SCAILE Technologies"),
        url="https://scaile.tech",
        industry=company_analysis.get("industry", "Answer Engine Optimization (AEO)"),
        description=company_analysis.get("description", "Answer Engine Optimization (AEO) services"),
        services=company_analysis.get("services", ["AEO content production", "AI visibility reporting"]),
        products=company_analysis.get("products", ["AEO software", "AI Visibility Engine"]),
        pain_points=company_analysis.get("pain_points", []),
        use_cases=company_analysis.get("use_cases", []),
        competitors=company_analysis.get("competitors", []),
        target_location=company_analysis.get("target_location", "United States"),
        target_audience=target_audience,
        brand_voice=company_analysis.get("brand_voice"),
        # Rich context from analysis
        customer_problems=company_analysis.get("customer_problems", []),
        value_propositions=company_analysis.get("value_propositions", []),
        differentiators=company_analysis.get("differentiators", []),
        key_features=company_analysis.get("key_features", []),
        solution_keywords=company_analysis.get("solution_keywords", []),
    )
    
    print("Step 2: Keyword Generation")
    print("-" * 80)
    
    config = GenerationConfig(
        target_count=20,
        min_score=70,
        enable_research=True,
        enable_serp_analysis=True,
        enable_enhanced_capture=True,
        enable_content_briefs=True,
        enable_citations=True,
        content_brief_count=15,
        research_sources_per_keyword=5,
        serp_sample_size=15,
    )
    
    print(f"Configuration:")
    print(f"   Target keywords: {config.target_count}")
    print(f"   Min score: {config.min_score}")
    print(f"   Enhanced capture: ✅")
    print(f"   Content briefs: ✅ ({config.content_brief_count})")
    print(f"   SERP analysis: ✅ ({config.serp_sample_size} keywords)")
    print()
    
    generator = KeywordGenerator(
        gemini_api_key=api_key,
        seranking_api_key=os.getenv("SERANKING_API_KEY"),
    )
    
    print("🚀 Starting generation...")
    import time
    start_time = time.time()
    
    result = await generator.generate(company_info=company, config=config)
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("📊 GENERATION RESULTS")
    print("=" * 80)
    print(f"⏱️  Time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"📝 Keywords generated: {len(result.keywords)}")
    print()
    
    # Analyze enhanced data
    keywords = result.keywords
    
    print("📈 Enhanced Data Coverage:")
    research_count = sum(1 for kw in keywords if kw.research_data)
    brief_count = sum(1 for kw in keywords if kw.content_brief)
    serp_count = sum(1 for kw in keywords if kw.serp_data)
    citations_count = sum(1 for kw in keywords if kw.citations)
    
    print(f"   Research data: {research_count}/{len(keywords)}")
    print(f"   Content briefs: {brief_count}/{len(keywords)}")
    print(f"   SERP data: {serp_count}/{len(keywords)}")
    print(f"   Citations: {citations_count}/{len(keywords)}")
    print()
    
    # Show top keywords
    print("🏆 Top 10 Keywords:")
    print()
    for i, kw in enumerate(keywords[:10], 1):
        print(f"{i}. {kw.keyword}")
        print(f"   Score: {kw.score}/100 | Intent: {kw.intent} | Volume: {kw.volume}")
        if kw.research_data:
            print(f"   🔬 Research: {len(kw.research_data.sources)} sources")
        if kw.content_brief:
            print(f"   📝 Brief: {len(kw.content_brief.target_questions)} questions")
        if kw.serp_data:
            print(f"   🔍 SERP: {len(kw.serp_data.organic_results)} results")
            # Check if URLs are real (not redirects)
            redirect_count = sum(1 for r in kw.serp_data.organic_results if "vertexaisearch" in r.url)
            if redirect_count > 0:
                print(f"   ⚠️  {redirect_count} redirect URLs still present")
            else:
                print(f"   ✅ All URLs resolved")
        if kw.citations:
            print(f"   📚 Citations: {len(kw.citations)}")
        print()
    
    # Check for issues
    print("=" * 80)
    print("🔍 QUALITY CHECKS")
    print("=" * 80)
    
    issues = []
    
    # Check 1: Research data null for research-sourced keywords
    research_sourced = [kw for kw in keywords if "research" in kw.source.lower()]
    research_without_data = [kw for kw in research_sourced if not kw.research_data]
    if research_without_data:
        issues.append(f"❌ {len(research_without_data)} research-sourced keywords missing research_data")
    
    # Check 2: Redirect URLs still present
    redirect_urls = []
    for kw in keywords:
        if kw.serp_data:
            for result in kw.serp_data.organic_results:
                if "vertexaisearch.cloud.google.com" in result.url:
                    redirect_urls.append(result.url)
    
    if redirect_urls:
        issues.append(f"⚠️  {len(redirect_urls)} redirect URLs still present (should be resolved)")
    else:
        print("✅ All URLs resolved (no redirect URLs)")
    
    # Check 3: Meta tags extraction
    meta_tags_count = sum(
        1 for kw in keywords 
        if kw.serp_data and any(r.meta_tags for r in kw.serp_data.organic_results)
    )
    print(f"{'✅' if meta_tags_count > 0 else '⚠️'} Meta tags extracted: {meta_tags_count} keywords have meta tags")
    
    if issues:
        print()
        for issue in issues:
            print(issue)
    else:
        print("✅ All quality checks passed!")
    
    # Export results
    print()
    print("=" * 80)
    print("💾 EXPORTING RESULTS")
    print("=" * 80)
    
    output_dir = Path("test-output")
    output_dir.mkdir(exist_ok=True)
    
    # JSON export
    json_path = output_dir / "scaile_full_test.json"
    result.to_json(str(json_path))
    print(f"✅ JSON: {json_path} ({json_path.stat().st_size / 1024:.1f} KB)")
    
    # CSV export
    csv_path = output_dir / "scaile_full_test.csv"
    result.to_csv(str(csv_path))
    print(f"✅ CSV: {csv_path} ({csv_path.stat().st_size / 1024:.1f} KB)")
    
    # Citations export
    citations_path = output_dir / "scaile_full_test_citations.md"
    result.export_citations(str(citations_path))
    print(f"✅ Citations: {citations_path} ({citations_path.stat().st_size / 1024:.1f} KB)")
    
    print()
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print()
    print(f"📁 Output files in: {output_dir.resolve()}")
    print(f"   - scaile_full_test.json (complete data)")
    print(f"   - scaile_full_test.csv (spreadsheet)")
    print(f"   - scaile_full_test_citations.md (citations)")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_scaile_full())

