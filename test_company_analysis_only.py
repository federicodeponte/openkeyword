#!/usr/bin/env python3
"""Test company analysis quality for SCAILE"""

import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)

from openkeywords.company_analyzer import analyze_company


async def test():
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print("=" * 80)
    print("🔍 COMPANY ANALYSIS TEST: scaile.tech")
    print("=" * 80)
    print()
    
    try:
        result = await analyze_company("https://scaile.tech", api_key=gemini_key)
        
        print(f"✅ Company Name: {result.get('company_name', 'N/A')}")
        print(f"✅ Industry: {result.get('industry', 'N/A')}")
        print(f"✅ Description: {result.get('description', 'N/A')[:200]}...")
        print()
        
        print("=" * 80)
        print(f"📦 PRODUCTS EXTRACTED ({len(result.get('products', []))}):")
        print("=" * 80)
        for i, p in enumerate(result.get('products', []), 1):
            print(f"{i}. {p}")
        print()
        
        print("=" * 80)
        print(f"🛠️  SERVICES EXTRACTED ({len(result.get('services', []))}):")
        print("=" * 80)
        for i, s in enumerate(result.get('services', []), 1):
            print(f"{i}. {s}")
        print()
        
        print("=" * 80)
        print(f"😰 PAIN POINTS ({len(result.get('pain_points', []))}):")
        print("=" * 80)
        for i, pp in enumerate(result.get('pain_points', []), 1):
            print(f"{i}. {pp}")
        print()
        
        if "solution_keywords" in result and result.get("solution_keywords"):
            print("=" * 80)
            print(f"🏷️  SOLUTION KEYWORDS:")
            print("=" * 80)
            print(", ".join(result.get("solution_keywords", [])[:10]))
            print()
        
        print("=" * 80)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())

