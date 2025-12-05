"""
OpenKeywords - Multi-Language Example

Demonstrates generating keywords in different languages.
No hardcoded language lists - supports ANY language dynamically.

Before running, set your API key:
    export GEMINI_API_KEY='your-gemini-api-key'

Run from project root:
    python examples/multilingual.py
"""

import asyncio
import os

from openkeywords import KeywordGenerator, CompanyInfo, GenerationConfig


async def generate_for_market(generator, company_name, language, region, industry, services):
    """Generate keywords for a specific market."""
    company = CompanyInfo(
        name=company_name,
        industry=industry,
        services=services,
        target_location=region.upper(),
    )

    config = GenerationConfig(
        target_count=15,
        min_score=50,
        enable_clustering=True,
        cluster_count=3,
        language=language,
        region=region,
    )

    print(f"\n{'='*60}")
    print(f"🌍 Market: {language.upper()} ({region.upper()})")
    print(f"   Company: {company_name}")
    print(f"{'='*60}")

    result = await generator.generate(company, config)

    print(f"\n✓ Generated {len(result.keywords)} keywords")
    print(f"  Average score: {result.statistics.avg_score:.1f}")

    print("\n📝 Keywords:")
    for kw in result.keywords[:10]:
        print(f"  • {kw.keyword} [{kw.intent}]")

    return result


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: Set GEMINI_API_KEY environment variable")
        return

    generator = KeywordGenerator()

    print("\n🔑 OpenKeywords - Multi-Language Demo")
    print("=" * 60)

    # English (US market)
    await generate_for_market(
        generator,
        company_name="TechCorp Solutions",
        language="english",
        region="us",
        industry="Cloud Software",
        services=["cloud hosting", "data storage", "backup solutions"],
    )

    # German (German market)
    await generate_for_market(
        generator,
        company_name="SCAILE Technologies GmbH",
        language="german",
        region="de",
        industry="AEO Marketing",
        services=["KI-Sichtbarkeit", "Content-Optimierung", "SEO"],
    )

    # Spanish (Mexico market)
    await generate_for_market(
        generator,
        company_name="Soluciones Digitales MX",
        language="spanish",
        region="mx",
        industry="Marketing Digital",
        services=["marketing digital", "publicidad en línea", "redes sociales"],
    )

    # French (France market)
    await generate_for_market(
        generator,
        company_name="Solutions Numériques FR",
        language="french",
        region="fr",
        industry="Services Numériques",
        services=["développement web", "applications mobiles", "conseil IT"],
    )

    print("\n" + "=" * 60)
    print("✓ Multi-language demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

