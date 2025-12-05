"""
OpenKeywords - Basic Usage Example

Before running, set your API key:
    export GEMINI_API_KEY='your-gemini-api-key'

Run from project root:
    python examples/basic_usage.py
"""

import asyncio
import os

from openkeywords import KeywordGenerator, CompanyInfo, GenerationConfig


async def main():
    # Check API key
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: Set GEMINI_API_KEY environment variable")
        print("  export GEMINI_API_KEY='your-key'")
        return

    # Initialize generator (uses GEMINI_API_KEY env var)
    generator = KeywordGenerator()

    # Define company information
    company = CompanyInfo(
        name="TechStartup.io",
        industry="B2B SaaS",
        description="Project management software for remote teams",
        services=["project management", "team collaboration", "task tracking"],
        products=["TechStartup Pro", "TechStartup Teams"],
        target_audience="small to medium businesses",
        target_location="United States",
    )

    # Configure generation
    config = GenerationConfig(
        target_count=30,           # Generate 30 keywords
        min_score=50,              # Only keep keywords scoring 50+
        enable_clustering=True,    # Group into semantic clusters
        cluster_count=5,           # Create 5 clusters
        language="english",        # Target language
        region="us",               # Target region
    )

    print(f"\n🔑 Generating keywords for {company.name}...")
    print(f"   Target: {config.target_count} keywords")
    print(f"   Language: {config.language} / Region: {config.region}\n")

    # Generate keywords
    result = await generator.generate(company, config)

    # Display results
    print(f"✓ Generated {len(result.keywords)} keywords in {result.processing_time_seconds:.1f}s")
    print(f"  Average score: {result.statistics.avg_score:.1f}")
    print(f"  Duplicates removed: {result.statistics.duplicate_count}")
    print(f"  Clusters: {len(result.clusters)}")

    print("\n📊 Intent Distribution:")
    for intent, count in result.statistics.intent_breakdown.items():
        pct = (count / len(result.keywords)) * 100 if result.keywords else 0
        print(f"   {intent}: {count} ({pct:.0f}%)")

    print("\n🏷️ Clusters:")
    for cluster in result.clusters:
        print(f"   {cluster.name}: {cluster.count} keywords")

    print("\n📝 Top 10 Keywords:")
    print("-" * 80)
    print(f"{'Keyword':<45} | {'Intent':<15} | {'Score':>5}")
    print("-" * 80)
    for kw in result.keywords[:10]:
        print(f"{kw.keyword:<45} | {kw.intent:<15} | {kw.score:>5}")

    # Export to files
    result.to_csv("keywords_output.csv")
    result.to_json("keywords_output.json")
    print("\n✓ Exported to keywords_output.csv and keywords_output.json")


if __name__ == "__main__":
    asyncio.run(main())
