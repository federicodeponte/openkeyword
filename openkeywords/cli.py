"""
OpenKeywords CLI - Generate SEO keywords from the command line.
"""

import asyncio
import logging
import os
import sys

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .generator import KeywordGenerator
from .models import CompanyInfo, GenerationConfig

console = Console()


def setup_logging(verbose: bool):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@click.group()
@click.version_option(version="0.1.0")
def main():
    """
    OpenKeywords - AI-powered SEO keyword generation.

    Generate high-quality, clustered SEO keywords using Google Gemini.
    Optionally fetch real search volume data from SE Ranking.
    """
    pass


@main.command()
@click.option("--company", "-c", default=None, help="Company name (or auto-detect from --url with --analyze-first)")
@click.option("--url", "-u", default="", help="Company website URL")
@click.option("--analyze-first", is_flag=True, help="Analyze company website first for rich context (requires --url)")
@click.option("--industry", "-i", default=None, help="Industry category")
@click.option("--description", "-d", default=None, help="Company description")
@click.option("--services", "-s", default=None, help="Services (comma-separated)")
@click.option("--products", "-p", default=None, help="Products (comma-separated)")
@click.option("--audience", "-a", default=None, help="Target audience")
@click.option("--location", "-l", default=None, help="Target location")
@click.option("--count", "-n", default=50, help="Number of keywords to generate")
@click.option("--clusters", default=6, help="Number of clusters")
@click.option("--language", default="english", help="Target language")
@click.option("--region", default="us", help="Target region (country code)")
@click.option("--min-score", default=40, help="Minimum company-fit score")
@click.option("--with-gaps", is_flag=True, help="Enable SE Ranking gap analysis (requires URL)")
@click.option("--with-research", is_flag=True, help="Enable deep research (Reddit, Quora, forums)")
@click.option("--research-focus", is_flag=True, help="Agency mode: 70%+ research keywords, strict filtering, 4+ word minimum")
@click.option("--with-serp", is_flag=True, help="Enable SERP analysis for AEO scoring (uses DataForSEO)")
@click.option("--serp-sample", default=15, help="Number of keywords to SERP analyze (default: 15)")
@click.option("--with-volume", is_flag=True, help="Get real search volumes from DataForSEO")
@click.option("--output", "-o", default=None, help="Output file (csv or json)")
@click.option("--competitors", default=None, help="Competitor URLs (comma-separated)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def generate(
    company: str,
    url: str,
    analyze_first: bool,
    industry: str,
    description: str,
    services: str,
    products: str,
    audience: str,
    location: str,
    count: int,
    clusters: int,
    language: str,
    region: str,
    min_score: int,
    with_gaps: bool,
    with_research: bool,
    research_focus: bool,
    with_serp: bool,
    serp_sample: int,
    with_volume: bool,
    competitors: str,
    output: str,
    verbose: bool,
):
    """
    Generate SEO keywords for a company.

    Examples:

        # Manual mode (you provide all details)
        openkeywords generate --company "Acme Software" --industry "B2B SaaS"

        openkeywords generate -c "Acme" -s "project management,collaboration" -n 100

        # Auto-analyze mode (extracts details from website)
        openkeywords generate --url "https://valoon.chat" --analyze-first -n 100

        openkeywords generate --url "https://acme.com" --analyze-first --with-research
    """
    setup_logging(verbose)

    # Check API keys
    if not os.getenv("GEMINI_API_KEY"):
        console.print("[red]Error: GEMINI_API_KEY environment variable not set[/red]")
        console.print("Set it with: export GEMINI_API_KEY='your-key'")
        sys.exit(1)

    # Check analyze-first requirements
    if analyze_first and not url:
        console.print("[red]Error: --url required when using --analyze-first[/red]")
        sys.exit(1)

    # Optional: Auto-analyze company website first
    if analyze_first and url:
        console.print(f"\n[bold magenta]🔍 Analyzing company website: {url}[/bold magenta]")
        console.print("[dim]This will extract products, pain points, differentiators, etc.[/dim]\n")
        
        try:
            from .company_analyzer import analyze_company
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing website...", total=None)
                
                async def run_analysis():
                    return await analyze_company(url)
                
                analysis = asyncio.run(run_analysis())
            
            console.print(f"[green]✓[/green] Analysis complete!")
            console.print(f"[dim]Company: {analysis.get('company_name', 'Unknown')}[/dim]")
            console.print(f"[dim]Industry: {analysis.get('industry', 'Unknown')}[/dim]")
            console.print(f"[dim]Products: {len(analysis.get('products', []))} found[/dim]")
            console.print(f"[dim]Pain points: {len(analysis.get('pain_points', []))} found[/dim]")
            console.print(f"[dim]Competitors: {len(analysis.get('competitors', []))} found[/dim]\n")
            
            # Use analysis results (override command-line params)
            company = company or analysis.get('company_name', 'Unknown')
            industry = industry or analysis.get('industry')
            description = description or analysis.get('description')
            
            # Extract products and services from analysis
            analyzed_products = analysis.get('products', [])
            analyzed_services = analysis.get('services', [])
            
            # Merge with command-line params (command-line takes precedence)
            if products:
                analyzed_products = products.split(",")
            if services:
                analyzed_services = services.split(",")
            
            # Extract target audience
            target_audiences = analysis.get('target_audience', [])
            if not audience and target_audiences:
                audience = ", ".join(target_audiences)
            
            # Extract competitors
            analyzed_competitors = [c for c in analysis.get('competitors', [])]
            if competitors:
                analyzed_competitors = competitors.split(",")
            
            # Build rich company info from analysis
            company_info = CompanyInfo(
                name=company,
                url=url,
                industry=industry,
                description=description,
                products=analyzed_products,
                services=analyzed_services,
                target_audience=audience,
                target_location=location,
                competitors=analyzed_competitors,
                # Rich context from analysis
                pain_points=analysis.get('pain_points', []),
                customer_problems=analysis.get('customer_problems', []),
                use_cases=analysis.get('use_cases', []),
                value_propositions=analysis.get('value_propositions', []),
                differentiators=analysis.get('differentiators', []),
                key_features=analysis.get('key_features', []),
                solution_keywords=analysis.get('solution_keywords', []),
                brand_voice=analysis.get('brand_voice'),
            )
            
        except Exception as e:
            console.print(f"[red]Error analyzing website: {e}[/red]")
            console.print("[yellow]Falling back to manual mode with provided parameters...[/yellow]\n")
            analyze_first = False
    
    # Manual mode: Build company info from command-line params
    if not analyze_first:
        if not company:
            console.print("[red]Error: --company required in manual mode (or use --url --analyze-first)[/red]")
            sys.exit(1)
        
        company_info = CompanyInfo(
            name=company,
            url=url,
            industry=industry,
            description=description,
            services=services.split(",") if services else [],
            products=products.split(",") if products else [],
            target_audience=audience,
            target_location=location,
            competitors=competitors.split(",") if competitors else [],
        )

    if with_gaps and not os.getenv("SERANKING_API_KEY"):
        console.print("[yellow]Warning: SERANKING_API_KEY not set - gap analysis will be skipped[/yellow]")
        with_gaps = False

    if with_gaps and not url:
        console.print("[yellow]Warning: --url required for gap analysis - skipping[/yellow]")
        with_gaps = False

    # Build config
    config = GenerationConfig(
        target_count=count,
        min_score=min_score,
        enable_clustering=True,
        cluster_count=clusters,
        language=language,
        region=region,
        enable_research=with_research or research_focus,  # research_focus implies research
        research_focus=research_focus,
        enable_serp_analysis=with_serp,
        serp_sample_size=serp_sample,
        enable_volume_lookup=with_volume,
    )

    console.print(f"\n[bold blue]🔑 OpenKeywords[/bold blue]")
    console.print(f"Generating {count} keywords for [green]{company_info.name}[/green]")
    if analyze_first:
        console.print("[bold magenta]🧠 Using rich company analysis (products, pain points, differentiators)[/bold magenta]")
    if research_focus:
        console.print("[bold red]🎯 RESEARCH FOCUS MODE: 70%+ research, 4+ words, strict filtering[/bold red]")
    elif with_research:
        console.print("[bold magenta]🔍 Deep Research enabled (Reddit, Quora, forums)[/bold magenta]")
    if with_serp:
        console.print(f"[bold cyan]📊 SERP Analysis enabled (top {serp_sample} keywords via DataForSEO)[/bold cyan]")
    if with_volume:
        console.print("[bold yellow]📈 Volume Lookup enabled (DataForSEO Keywords Data API)[/bold yellow]")
    console.print()

    # Run generation
    async def run():
        generator = KeywordGenerator()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Generating keywords...", total=None)
            result = await generator.generate(company_info, config)

        return result

    try:
        result = asyncio.run(run())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    # Display results
    console.print(f"\n[green]✓ Generated {len(result.keywords)} keywords[/green]")
    console.print(f"  Processing time: {result.processing_time_seconds:.1f}s")
    console.print(f"  Average score: {result.statistics.avg_score:.1f}")
    console.print(f"  Clusters: {len(result.clusters)}")

    # Source breakdown (if research was enabled)
    if result.statistics.source_breakdown and len(result.statistics.source_breakdown) > 1:
        console.print("\n[bold]Keyword Sources:[/bold]")
        for source, src_count in result.statistics.source_breakdown.items():
            pct = (src_count / len(result.keywords)) * 100 if result.keywords else 0
            icon = "🔍" if "research" in source else "🤖" if source == "ai_generated" else "📊"
            console.print(f"  {icon} {source}: {src_count} ({pct:.0f}%)")

    # Intent breakdown
    if result.statistics.intent_breakdown:
        console.print("\n[bold]Intent Distribution:[/bold]")
        for intent, int_count in result.statistics.intent_breakdown.items():
            pct = (int_count / len(result.keywords)) * 100 if result.keywords else 0
            console.print(f"  {intent}: {int_count} ({pct:.0f}%)")

    # Show top keywords
    console.print("\n[bold]Top 10 Keywords:[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Keyword", style="cyan")
    table.add_column("Intent", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Cluster", style="yellow")

    if with_gaps or with_volume:
        table.add_column("Volume", justify="right")
        table.add_column("Difficulty", justify="right")

    if with_serp:
        table.add_column("AEO", justify="right", style="bold green")
        table.add_column("FS", justify="center")  # Featured Snippet
        table.add_column("PAA", justify="center")  # People Also Ask

    if with_research or with_gaps:
        table.add_column("Source", style="magenta")

    for kw in result.keywords[:10]:
        row = [
            kw.keyword,
            kw.intent,
            str(kw.score),
            kw.cluster_name or "-",
        ]
        if with_gaps or with_volume:
            vol_str = f"{kw.volume:,}" if kw.volume > 0 else "-"
            row.extend([vol_str, str(kw.difficulty)])
        if with_serp:
            aeo_str = str(kw.aeo_opportunity) if kw.serp_analyzed else "-"
            fs_str = "✅" if kw.has_featured_snippet else "-"
            paa_str = "✅" if kw.has_paa else "-"
            row.extend([aeo_str, fs_str, paa_str])
        if with_research or with_gaps:
            # Shorten source name for display
            src = kw.source.replace("research_", "📍").replace("ai_generated", "🤖").replace("gap_analysis", "📊").replace("serp_paa", "📝")
            row.append(src)
        table.add_row(*row)

    console.print(table)
    
    # Show AEO summary if SERP analysis was enabled
    if with_serp:
        analyzed = [kw for kw in result.keywords if kw.serp_analyzed]
        if analyzed:
            high_aeo = [kw for kw in analyzed if kw.aeo_opportunity >= 70]
            with_fs = [kw for kw in analyzed if kw.has_featured_snippet]
            with_paa = [kw for kw in analyzed if kw.has_paa]
            console.print(f"\n[bold cyan]📊 AEO Summary:[/bold cyan]")
            console.print(f"  Analyzed: {len(analyzed)} keywords")
            console.print(f"  High AEO opportunity (≥70): {len(high_aeo)}")
            console.print(f"  With Featured Snippet: {len(with_fs)}")
            console.print(f"  With People Also Ask: {len(with_paa)}")

    # Export if output specified
    if output:
        if output.endswith(".csv"):
            result.to_csv(output)
            console.print(f"\n[green]✓ Exported to {output}[/green]")
        elif output.endswith(".json"):
            result.to_json(output)
            console.print(f"\n[green]✓ Exported to {output}[/green]")
        else:
            console.print(f"[yellow]Unknown format. Use .csv or .json extension.[/yellow]")


@main.command()
def check():
    """
    Check API key configuration.
    """
    console.print("\n[bold blue]🔑 OpenKeywords - Configuration Check[/bold blue]\n")

    gemini_key = os.getenv("GEMINI_API_KEY")
    seranking_key = os.getenv("SERANKING_API_KEY")
    dataforseo_login = os.getenv("DATAFORSEO_LOGIN")
    dataforseo_password = os.getenv("DATAFORSEO_PASSWORD")

    console.print("[bold]Required:[/bold]")
    if gemini_key:
        console.print(f"  [green]✓[/green] GEMINI_API_KEY: Set ({gemini_key[:8]}...)")
    else:
        console.print("  [red]✗[/red] GEMINI_API_KEY: Not set")

    console.print("\n[bold]Optional (for enhanced features):[/bold]")
    
    if seranking_key:
        console.print(f"  [green]✓[/green] SERANKING_API_KEY: Set ({seranking_key[:8]}...) → gap analysis")
    else:
        console.print("  [yellow]○[/yellow] SERANKING_API_KEY: Not set → --with-gaps disabled")

    if dataforseo_login and dataforseo_password:
        console.print(f"  [green]✓[/green] DATAFORSEO_LOGIN: Set ({dataforseo_login[:8]}...) → SERP analysis")
        console.print(f"  [green]✓[/green] DATAFORSEO_PASSWORD: Set → SERP analysis")
    else:
        console.print("  [yellow]○[/yellow] DATAFORSEO_LOGIN/PASSWORD: Not set → --with-serp disabled")

    console.print("\n[bold]Setup Instructions:[/bold]")
    console.print("  # Required")
    console.print("  export GEMINI_API_KEY='your-gemini-api-key'")
    console.print("")
    console.print("  # Optional: SE Ranking for gap analysis")
    console.print("  export SERANKING_API_KEY='your-seranking-key'")
    console.print("")
    console.print("  # Optional: DataForSEO for SERP/AEO analysis")
    console.print("  export DATAFORSEO_LOGIN='your-email'")
    console.print("  export DATAFORSEO_PASSWORD='your-password'")


if __name__ == "__main__":
    main()


