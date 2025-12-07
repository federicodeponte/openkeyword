"""
Google Trends analyzer for FREE keyword research with trend data and rising queries.
Uses pytrends (unofficial but stable Google Trends API).
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrendData:
    """Trend data for a keyword."""
    keyword: str
    
    # Interest level (0-100, relative popularity)
    current_interest: int = 0
    avg_interest: float = 0.0
    peak_interest: int = 0
    
    # Trend direction
    trend_direction: str = "stable"  # "rising", "falling", "stable"
    trend_percentage: float = 0.0  # % change vs previous period
    
    # Seasonality
    is_seasonal: bool = False
    peak_months: List[str] = field(default_factory=list)
    
    # Related searches
    top_related: List[Dict[str, any]] = field(default_factory=list)
    rising_related: List[Dict[str, any]] = field(default_factory=list)
    
    # Regional data
    top_regions: List[Dict[str, any]] = field(default_factory=list)
    
    # Time series
    historical_data: Dict[str, int] = field(default_factory=dict)


class GoogleTrendsAnalyzer:
    """
    Analyze keyword trends using Google Trends (pytrends).
    
    Features:
    - Interest over time (0-100 relative scale)
    - Rising queries (trending keywords - GOLD!)
    - Top related searches
    - Regional interest
    - Seasonality detection
    
    100% FREE - no API key required!
    
    Usage:
        analyzer = GoogleTrendsAnalyzer(country='US', language='en')
        trend_data = await analyzer.analyze_keywords(['what is SEO'])
        
        for keyword, data in trend_data.items():
            print(f"{keyword}: Interest={data.current_interest}/100")
            print(f"  Rising queries: {len(data.rising_related)}")
    """
    
    def __init__(
        self,
        country: str = "US",
        language: str = "en",
        timeframe: str = "today 12-m",
        max_concurrent: int = 3,
    ):
        """
        Initialize Google Trends analyzer.
        
        Args:
            country: Country code (e.g., 'US', 'GB', 'DE')
            language: Language code (e.g., 'en', 'de', 'es')
            timeframe: Time range for trends (default: past 12 months)
                      Options: 'now 1-H', 'now 4-H', 'today 1-m', 'today 3-m',
                               'today 12-m', 'today 5-y', 'all'
            max_concurrent: Max concurrent trend requests
        """
        self.country = country.upper()
        self.language = language.lower()
        self.timeframe = timeframe
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pytrends = None
        
        logger.info(f"Google Trends Analyzer initialized (country={country}, timeframe={timeframe})")
    
    def _get_pytrends(self):
        """Lazy load pytrends."""
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq
                self._pytrends = TrendReq(
                    hl=f'{self.language}-{self.country}',
                    tz=360,
                )
            except ImportError:
                raise ImportError(
                    "pytrends is required for Google Trends analysis. "
                    "Install with: pip install pytrends"
                )
        return self._pytrends
    
    async def analyze_keywords(
        self,
        keywords: List[str],
        extract_related: bool = True,
        extract_regional: bool = True,
    ) -> Dict[str, TrendData]:
        """
        Analyze multiple keywords for trend data.
        
        Args:
            keywords: List of keywords to analyze (max 5 at a time per API limitation)
            extract_related: Extract related and rising queries
            extract_regional: Extract regional interest data
            
        Returns:
            Dict mapping keyword -> TrendData
        """
        if not keywords:
            return {}
        
        logger.info(f"Analyzing trends for {len(keywords)} keywords...")
        
        # Google Trends API limits to 5 keywords per request
        # Split into batches
        batches = [keywords[i:i+5] for i in range(0, len(keywords), 5)]
        
        all_results = {}
        for batch in batches:
            batch_results = await self._analyze_batch(
                batch,
                extract_related=extract_related,
                extract_regional=extract_regional
            )
            all_results.update(batch_results)
        
        logger.info(f"Trends analysis complete for {len(all_results)} keywords")
        
        return all_results
    
    async def _analyze_batch(
        self,
        keywords: List[str],
        extract_related: bool,
        extract_regional: bool,
    ) -> Dict[str, TrendData]:
        """Analyze a batch of keywords (max 5)."""
        async with self._semaphore:
            # Run in thread pool (pytrends is blocking)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._analyze_batch_sync,
                keywords,
                extract_related,
                extract_regional
            )
    
    def _analyze_batch_sync(
        self,
        keywords: List[str],
        extract_related: bool,
        extract_regional: bool,
    ) -> Dict[str, TrendData]:
        """Synchronous batch analysis."""
        pytrends = self._get_pytrends()
        results = {}
        
        try:
            # Build payload
            pytrends.build_payload(
                keywords,
                cat=0,
                timeframe=self.timeframe,
                geo=self.country,
            )
            
            # Get interest over time
            interest_df = pytrends.interest_over_time()
            
            for keyword in keywords:
                trend_data = TrendData(keyword=keyword)
                
                if not interest_df.empty and keyword in interest_df.columns:
                    # Interest metrics
                    series = interest_df[keyword]
                    trend_data.current_interest = int(series.iloc[-1])
                    trend_data.avg_interest = float(series.mean())
                    trend_data.peak_interest = int(series.max())
                    
                    # Trend direction (compare recent vs older)
                    recent = series.tail(3).mean()
                    older = series.head(3).mean()
                    if older > 0:
                        trend_data.trend_percentage = ((recent - older) / older) * 100
                        if trend_data.trend_percentage > 10:
                            trend_data.trend_direction = "rising"
                        elif trend_data.trend_percentage < -10:
                            trend_data.trend_direction = "falling"
                    
                    # Seasonality detection (simple: check if variance is high)
                    if len(series) >= 12:
                        monthly_avg = series.groupby(series.index.month).mean()
                        if monthly_avg.std() > 15:  # High variance = seasonal
                            trend_data.is_seasonal = True
                            # Find peak months
                            top_months = monthly_avg.nlargest(3)
                            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                            trend_data.peak_months = [month_names[m-1] for m in top_months.index]
                    
                    # Historical data
                    trend_data.historical_data = {
                        str(date): int(value)
                        for date, value in series.items()
                    }
                
                # Related queries
                if extract_related:
                    try:
                        related = pytrends.related_queries()
                        if keyword in related:
                            # Top related
                            if related[keyword]['top'] is not None:
                                top_df = related[keyword]['top']
                                trend_data.top_related = [
                                    {'query': row['query'], 'value': row['value']}
                                    for _, row in top_df.head(10).iterrows()
                                ]
                            
                            # Rising related (GOLD MINE!)
                            if related[keyword]['rising'] is not None:
                                rising_df = related[keyword]['rising']
                                trend_data.rising_related = [
                                    {'query': row['query'], 'value': row['value']}
                                    for _, row in rising_df.head(10).iterrows()
                                ]
                    except Exception as e:
                        logger.warning(f"Failed to get related queries for '{keyword}': {e}")
                
                # Regional interest
                if extract_regional:
                    try:
                        regions = pytrends.interest_by_region(resolution='COUNTRY')
                        if keyword in regions.columns:
                            top_regions = regions.nlargest(5, keyword)[keyword]
                            trend_data.top_regions = [
                                {'region': region, 'interest': int(interest)}
                                for region, interest in top_regions.items()
                                if interest > 0
                            ]
                    except Exception as e:
                        logger.warning(f"Failed to get regional data for '{keyword}': {e}")
                
                results[keyword] = trend_data
        
        except Exception as e:
            logger.error(f"Trends analysis failed for batch: {e}")
            # Return empty TrendData for each keyword
            for keyword in keywords:
                results[keyword] = TrendData(keyword=keyword)
        
        return results
    
    async def get_rising_keywords(
        self,
        seed_keywords: List[str],
        min_growth: int = 100,  # % growth threshold
    ) -> List[str]:
        """
        Get rising/trending keywords related to seed keywords.
        
        This is GOLD for finding hot topics!
        
        Args:
            seed_keywords: Starting keywords
            min_growth: Minimum growth % to include (default: 100% = doubled)
            
        Returns:
            List of rising keyword strings
        """
        trend_data = await self.analyze_keywords(seed_keywords, extract_related=True)
        
        rising_keywords = []
        for keyword, data in trend_data.items():
            for item in data.rising_related:
                # Check if it's a "Breakout" (massive growth) or meets threshold
                value = item['value']
                if value == 'Breakout':
                    rising_keywords.append(item['query'])
                elif isinstance(value, (int, float)) and value >= min_growth:
                    rising_keywords.append(item['query'])
        
        return list(set(rising_keywords))  # Remove duplicates


async def analyze_trends(
    keywords: List[str],
    country: str = "US",
    language: str = "en",
    timeframe: str = "today 12-m",
) -> Dict[str, TrendData]:
    """
    Convenience function to analyze keyword trends.
    
    Args:
        keywords: Keywords to analyze
        country: Country code
        language: Language code
        timeframe: Time range for analysis
        
    Returns:
        Dict mapping keyword -> TrendData
    """
    analyzer = GoogleTrendsAnalyzer(
        country=country,
        language=language,
        timeframe=timeframe,
    )
    return await analyzer.analyze_keywords(keywords)


# CLI for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        keywords = sys.argv[1:] if len(sys.argv) > 1 else [
            "what is SEO",
            "AI SEO tools",
            "answer engine optimization",
        ]
        
        print(f"\n📈 Analyzing Google Trends for {len(keywords)} keywords...\n")
        
        trend_data = await analyze_trends(keywords)
        
        for kw, data in trend_data.items():
            print(f"━━━ {kw} ━━━")
            print(f"  Current Interest: {data.current_interest}/100")
            print(f"  Average Interest: {data.avg_interest:.1f}/100")
            print(f"  Trend: {data.trend_direction} ({data.trend_percentage:+.1f}%)")
            
            if data.is_seasonal:
                print(f"  Seasonality: ✅ Peaks in {', '.join(data.peak_months)}")
            
            if data.top_related:
                print(f"  Top Related ({len(data.top_related)}):")
                for item in data.top_related[:3]:
                    print(f"    • {item['query']} ({item['value']})")
            
            if data.rising_related:
                print(f"  🔥 Rising Queries ({len(data.rising_related)}):")
                for item in data.rising_related[:3]:
                    value = item['value']
                    if value == 'Breakout':
                        print(f"    🚀 {item['query']} (BREAKOUT!)")
                    else:
                        print(f"    📈 {item['query']} (+{value}%)")
            
            if data.top_regions:
                print(f"  Top Regions:")
                for item in data.top_regions[:3]:
                    print(f"    🌍 {item['region']}: {item['interest']}/100")
            
            print()
    
    asyncio.run(main())

