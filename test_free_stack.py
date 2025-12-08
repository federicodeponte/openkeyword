#!/usr/bin/env python3
"""
Comprehensive test of OpenKeywords FREE keyword research stack.
Tests: Autocomplete + Google Trends + Gemini SERP
"""
import asyncio
import sys
from datetime import datetime

# Test keyword
TEST_KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "AI SEO"

print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║       🧪 OpenKeywords FREE Stack Test                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

Testing keyword: "{TEST_KEYWORD}"
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

""")

async def test_all():
    results = {
        'autocomplete': None,
        'trends': None,
        'gemini': None,
        'timings': {},
    }
    
    # ─────────────────────────────────────────────────────────────
    # Test 1: Google Autocomplete (Fastest)
    # ─────────────────────────────────────────────────────────────
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 1️⃣  GOOGLE AUTOCOMPLETE                                 │")
    print("└─────────────────────────────────────────────────────────┘")
    
    try:
        from openkeywords.autocomplete_analyzer import get_autocomplete_suggestions
        
        start = datetime.now()
        result = await get_autocomplete_suggestions(TEST_KEYWORD, include_questions=True)
        duration = (datetime.now() - start).total_seconds()
        results['timings']['autocomplete'] = duration
        results['autocomplete'] = result
        
        print(f"⏱️  Time: {duration:.2f}s")
        print(f"✅ Total suggestions: {len(result.suggestions)}")
        print(f"❓ Question keywords: {len(result.question_keywords)}")
        print(f"📝 Long-tail (3+ words): {len(result.long_tail_keywords)}")
        
        if result.suggestions:
            print(f"\n🔝 Top 10 suggestions:")
            for i, suggestion in enumerate(result.suggestions[:10], 1):
                icon = "❓" if suggestion in result.question_keywords else "🔹"
                print(f"   {i:2}. {icon} {suggestion}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}\n")
        results['autocomplete'] = None
    
    # ─────────────────────────────────────────────────────────────
    # Test 2: Google Trends
    # ─────────────────────────────────────────────────────────────
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 2️⃣  GOOGLE TRENDS                                       │")
    print("└─────────────────────────────────────────────────────────┘")
    
    try:
        from openkeywords.google_trends_analyzer import analyze_trends
        
        start = datetime.now()
        trend_data = await analyze_trends([TEST_KEYWORD], timeframe='today 12-m')
        duration = (datetime.now() - start).total_seconds()
        results['timings']['trends'] = duration
        results['trends'] = trend_data
        
        data = trend_data[TEST_KEYWORD]
        
        print(f"⏱️  Time: {duration:.2f}s")
        print(f"📊 Current interest: {data.current_interest}/100")
        print(f"📈 Average interest: {data.avg_interest:.1f}/100")
        print(f"🎯 Peak interest: {data.peak_interest}/100")
        print(f"📉 Trend: {data.trend_direction.upper()} ({data.trend_percentage:+.1f}%)")
        
        if data.is_seasonal:
            print(f"🌊 Seasonality: ✅ Peaks in {', '.join(data.peak_months)}")
        
        if data.rising_related:
            print(f"\n🔥 Rising queries (TRENDING!):")
            for i, item in enumerate(data.rising_related[:5], 1):
                value = item['value']
                if value == 'Breakout':
                    print(f"   {i}. 🚀 {item['query']} (BREAKOUT!)")
                else:
                    print(f"   {i}. 📈 {item['query']} (+{value}%)")
        
        if data.top_related:
            print(f"\n🔗 Top related queries:")
            for i, item in enumerate(data.top_related[:5], 1):
                print(f"   {i}. {item['query']} ({item['value']})")
        
        if data.top_regions:
            print(f"\n🌍 Top regions:")
            for i, item in enumerate(data.top_regions[:3], 1):
                print(f"   {i}. {item['region']}: {item['interest']}/100")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}\n")
        results['trends'] = None
    
    # ─────────────────────────────────────────────────────────────
    # Test 3: Gemini SERP Analysis (if API key available)
    # ─────────────────────────────────────────────────────────────
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 3️⃣  GEMINI SERP ANALYSIS                                │")
    print("└─────────────────────────────────────────────────────────┘")
    
    try:
        import os
        if not os.getenv('GEMINI_API_KEY'):
            print("⚠️  Skipped: GEMINI_API_KEY not set")
            print("   Set GEMINI_API_KEY to test SERP analysis\n")
        else:
            from openkeywords.gemini_serp_analyzer import analyze_for_aeo_gemini
            
            start = datetime.now()
            analyses, bonus = await analyze_for_aeo_gemini([TEST_KEYWORD])
            duration = (datetime.now() - start).total_seconds()
            results['timings']['gemini'] = duration
            results['gemini'] = analyses
            
            analysis = analyses[TEST_KEYWORD]
            features = analysis.features
            
            print(f"⏱️  Time: {duration:.2f}s")
            print(f"🎯 AEO Score: {features.aeo_opportunity}/100")
            print(f"💡 Reason: {features.aeo_reason}")
            print(f"✨ Featured Snippet: {'✅' if features.has_featured_snippet else '❌'}")
            print(f"❓ PAA Questions: {len(features.paa_questions)}")
            print(f"📊 Volume: {features.volume_estimate or 'N/A'}")
            
            if features.paa_questions:
                print(f"\n❓ PAA Questions:")
                for i, q in enumerate(features.paa_questions[:3], 1):
                    print(f"   {i}. {q}")
            
            if features.related_searches:
                print(f"\n🔗 Related searches:")
                for i, r in enumerate(features.related_searches[:3], 1):
                    print(f"   {i}. {r}")
            
            if bonus:
                print(f"\n🎁 Bonus keywords: {len(bonus)}")
            
            print()
    
    except Exception as e:
        print(f"❌ Error: {e}\n")
        results['gemini'] = None
    
    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                       📊 SUMMARY                          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    # Timings
    total_time = sum(results['timings'].values())
    print("⏱️  Performance:")
    for service, duration in results['timings'].items():
        print(f"   • {service.title():15} {duration:.2f}s")
    if total_time > 0:
        print(f"   • {'Total':15} {total_time:.2f}s")
    print()
    
    # Data collected
    print("📦 Data collected:")
    if results['autocomplete']:
        print(f"   ✅ Autocomplete: {len(results['autocomplete'].suggestions)} suggestions")
    else:
        print(f"   ❌ Autocomplete: Failed")
    
    if results['trends']:
        data = results['trends'][TEST_KEYWORD]
        rising_count = len(data.rising_related) if data.rising_related else 0
        print(f"   ✅ Trends: {rising_count} rising queries")
    else:
        print(f"   ❌ Trends: Failed")
    
    if results['gemini']:
        analysis = results['gemini'][TEST_KEYWORD]
        if analysis.error:
            print(f"   ❌ Gemini: {analysis.error}")
        else:
            print(f"   ✅ Gemini: AEO score {analysis.features.aeo_opportunity}/100")
    else:
        print(f"   ⚠️  Gemini: Skipped (no API key)")
    
    print()
    
    # Cost estimate
    print("💰 Cost estimate:")
    print(f"   • Autocomplete:  $0.00 (FREE)")
    print(f"   • Trends:        $0.00 (FREE)")
    if results['gemini']:
        print(f"   • Gemini:        ~$0.002 (1 keyword)")
        print(f"   • Total:         ~$0.002")
    else:
        print(f"   • Gemini:        $0.00 (skipped)")
        print(f"   • Total:         $0.00 (100% FREE!)")
    print()
    
    # Combined insights
    if results['autocomplete'] and results['trends']:
        print("🎯 Combined insights:")
        
        # Find overlapping keywords
        autocomplete_set = set(s.lower() for s in results['autocomplete'].suggestions)
        
        if results['trends']:
            trend_data = results['trends'][TEST_KEYWORD]
            if trend_data.rising_related:
                rising_set = set(r['query'].lower() for r in trend_data.rising_related)
                overlap = autocomplete_set & rising_set
                if overlap:
                    print(f"   🔥 {len(overlap)} keywords are BOTH trending AND suggested!")
                    for kw in list(overlap)[:3]:
                        print(f"      • {kw}")
        
        # Question keywords count
        question_count = len(results['autocomplete'].question_keywords)
        print(f"   ❓ {question_count} question keywords (great for AEO)")
        
        # Long-tail count
        long_tail_count = len(results['autocomplete'].long_tail_keywords)
        print(f"   📝 {long_tail_count} long-tail keywords (3+ words)")
        
        print()
    
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    ✅ TEST COMPLETE                       ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    if not results['gemini']:
        print("💡 Tip: Set GEMINI_API_KEY to test SERP analysis:")
        print("   export GEMINI_API_KEY='your_key'")
        print("   python3 test_free_stack.py")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_all())

