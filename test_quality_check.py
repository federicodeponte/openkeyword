#!/usr/bin/env python3
"""Quality check: Verify company analysis + keyword quality for SCAILE"""

import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)

from openkeywords.company_analyzer import analyze_company
from openkeywords.models import CompanyInfo, GenerationConfig
from openkeywords.generator import KeywordGenerator


async def test():
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print("=" * 80)
    print("🔍 QUALITY CHECK: SCAILE.TECH")
    print("=" * 80)
    print()
    
    # Step 1: Company Analysis
    print("STEP 1: Company Analysis")
    print("-" * 80)
    try:
        company_data = await analyze_company("https://scaile.tech", api_key=gemini_key)
        
        print(f"✅ Company: {company_data.get('company_name', 'N/A')}")
        print(f"✅ Industry: {company_data.get('industry', 'N/A')}")
        print()
        
        # Check target_audience (critical for company size modifiers)
        target_audience = company_data.get('target_audience', [])
        print(f"📊 TARGET AUDIENCE (for hyper-niche size modifiers):")
        if target_audience:
            if isinstance(target_audience, list):
                for i, aud in enumerate(target_audience, 1):
                    print(f"   {i}. {aud}")
                
                # Check for company size indicators
                audience_str = " ".join(target_audience).lower()
                has_startup = any(x in audience_str for x in ["startup", "smb", "sme", "small business"])
                has_enterprise = any(x in audience_str for x in ["enterprise", "fortune 500", "large company"])
                
                if has_startup:
                    print(f"   ✅ Contains startup/SME indicators")
                if has_enterprise:
                    print(f"   ✅ Contains enterprise indicators")
                if not has_startup and not has_enterprise:
                    print(f"   ⚠️  No clear company size indicators found")
            else:
                print(f"   {target_audience}")
        else:
            print(f"   ❌ No target_audience extracted!")
        print()
        
        # Check primary_region (critical for geo modifiers)
        primary_region = company_data.get('primary_region', '')
        print(f"🌍 PRIMARY REGION (for hyper-niche geo modifiers):")
        if primary_region:
            print(f"   {primary_region}")
            region_lower = primary_region.lower()
            is_specific = any(x in region_lower for x in ["germany", "uk", "france", "spain", "italy", "dach", "benelux", "nordics", "apac"])
            is_us_global = any(x in region_lower for x in ["us", "united states", "usa", "global", "worldwide"])
            
            if is_specific:
                print(f"   ✅ Specific region identified (good for geo targeting)")
            elif is_us_global:
                print(f"   ⚠️  US/Global (geo modifiers will be skipped)")
        else:
            print(f"   ❌ No primary_region extracted!")
        print()
        
        print(f"📦 PRODUCTS ({len(company_data.get('products', []))}):")
        for i, p in enumerate(company_data.get('products', [])[:3], 1):
            print(f"   {i}. {p}")
        print()
        
        print(f"🛠️  SERVICES ({len(company_data.get('services', []))}):")
        for i, s in enumerate(company_data.get('services', [])[:3], 1):
            print(f"   {i}. {s}")
        print()
        
    except Exception as e:
        print(f"❌ Company analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Generate Sample Keywords
    print("=" * 80)
    print("STEP 2: Generate Sample Keywords (15 keywords)")
    print("-" * 80)
    print()
    
    try:
        # Build CompanyInfo
        company = CompanyInfo(
            name=company_data.get("company_name", "SCAILE"),
            url="https://scaile.tech",
            industry=company_data.get("industry", "AI & SEO"),
            description=company_data.get("description", ""),
            services=company_data.get("services", []),
            products=company_data.get("products", []),
            pain_points=company_data.get("pain_points", []),
            use_cases=company_data.get("use_cases", []),
            competitors=company_data.get("competitors", []),
            target_location=company_data.get("primary_region"),
            target_audience=", ".join(company_data.get("target_audience", [])) if isinstance(company_data.get("target_audience"), list) else company_data.get("target_audience"),
            brand_voice=company_data.get("brand_voice"),
        )
        
        # Generate 15 keywords (fast, no research, no SERP)
        config = GenerationConfig(
            target_count=15,
            min_score=70,
            enable_research=False,
            enable_serp_analysis=False,
            enable_enhanced_capture=False,
            min_word_count=3,  # Prefer longer keywords
        )
        
        generator = KeywordGenerator(gemini_api_key=gemini_key)
        result = await generator.generate(company_info=company, config=config)
        
        print(f"✅ Generated {len(result.keywords)} keywords")
        print()
        
        # Analyze keyword quality
        print("=" * 80)
        print("📝 KEYWORD QUALITY ANALYSIS")
        print("=" * 80)
        print()
        
        keywords = result.keywords[:15]
        
        # Check for product name keywords (BAD)
        product_names = [p.lower() for p in company_data.get('products', [])]
        service_names = [s.lower() for s in company_data.get('services', [])]
        
        product_keywords = []
        natural_keywords = []
        hyper_niche_keywords = []
        
        for kw in keywords:
            kw_lower = kw.keyword.lower()
            
            # Check if it's a product name keyword (bad)
            is_product_kw = any(prod in kw_lower for prod in product_names if prod)
            if is_product_kw:
                product_keywords.append(kw)
            else:
                natural_keywords.append(kw)
            
            # Check if it's hyper-niche (has geo/size/industry modifiers)
            has_size_modifier = any(x in kw_lower for x in ["startup", "sme", "enterprise", "small business", "mid-size"])
            has_geo_modifier = any(x in kw_lower for x in ["germany", "uk", "europe", "us", "berlin", "london"])
            has_industry_modifier = any(x in kw_lower for x in ["saas", "b2b", "fintech", "martech", "cybersecurity", "ecommerce"])
            
            if has_size_modifier or has_geo_modifier or has_industry_modifier:
                hyper_niche_keywords.append(kw)
        
        # Display results
        print(f"✅ Natural searcher keywords: {len(natural_keywords)}/{len(keywords)} ({len(natural_keywords)/len(keywords)*100:.0f}%)")
        print(f"⚠️  Product-name keywords: {len(product_keywords)}/{len(keywords)} ({len(product_keywords)/len(keywords)*100:.0f}%)")
        print(f"🎯 Hyper-niche keywords: {len(hyper_niche_keywords)}/{len(keywords)} ({len(hyper_niche_keywords)/len(keywords)*100:.0f}%)")
        print()
        
        # Show examples
        if natural_keywords:
            print("✅ NATURAL KEYWORDS (Good):")
            for i, kw in enumerate(natural_keywords[:5], 1):
                word_count = len(kw.keyword.split())
                print(f"   {i}. {kw.keyword} ({word_count} words, {kw.intent})")
            print()
        
        if product_keywords:
            print("⚠️  PRODUCT-NAME KEYWORDS (Should be minimal):")
            for i, kw in enumerate(product_keywords[:3], 1):
                print(f"   {i}. {kw.keyword}")
            print()
        
        if hyper_niche_keywords:
            print("🎯 HYPER-NICHE KEYWORDS (Geo/Size/Industry modifiers):")
            for i, kw in enumerate(hyper_niche_keywords[:5], 1):
                word_count = len(kw.keyword.split())
                modifiers = []
                if any(x in kw.keyword.lower() for x in ["startup", "sme", "enterprise"]):
                    modifiers.append("size")
                if any(x in kw.keyword.lower() for x in ["germany", "uk", "europe", "us"]):
                    modifiers.append("geo")
                if any(x in kw.keyword.lower() for x in ["saas", "b2b", "fintech", "martech"]):
                    modifiers.append("industry")
                print(f"   {i}. {kw.keyword} ({word_count} words, modifiers: {', '.join(modifiers)})")
            print()
        else:
            print("❌ NO HYPER-NICHE KEYWORDS FOUND!")
            print("   This suggests target_audience or primary_region extraction failed.")
            print()
        
        # Final verdict
        print("=" * 80)
        print("📊 VERDICT")
        print("=" * 80)
        print()
        
        issues = []
        
        if not target_audience:
            issues.append("❌ No target_audience extracted (needed for size modifiers)")
        
        if not primary_region:
            issues.append("❌ No primary_region extracted (needed for geo modifiers)")
        
        if len(product_keywords) > len(keywords) * 0.3:
            issues.append(f"⚠️  Too many product-name keywords ({len(product_keywords)}/{len(keywords)})")
        
        if len(hyper_niche_keywords) < len(keywords) * 0.2:
            issues.append(f"⚠️  Too few hyper-niche keywords ({len(hyper_niche_keywords)}/{len(keywords)}, expected 20%+)")
        
        if len(natural_keywords) < len(keywords) * 0.7:
            issues.append(f"⚠️  Too few natural keywords ({len(natural_keywords)}/{len(keywords)}, expected 70%+)")
        
        if issues:
            print("⚠️  ISSUES FOUND:")
            for issue in issues:
                print(f"   {issue}")
            print()
            print("❌ NOT 110% HAPPY YET - Need fixes")
        else:
            print("✅ ALL CHECKS PASSED!")
            print()
            print("✅ 110% HAPPY - Ready to ship! 🚀")
        
    except Exception as e:
        print(f"❌ Keyword generation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())

