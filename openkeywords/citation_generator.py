#!/usr/bin/env python3
"""
Citation Generator for OpenKeywords
Generates citations in APA, MLA, and Chicago formats from research sources and SERP data.
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CitationGenerator:
    """Generate citations in multiple formats from research and SERP data."""
    
    def __init__(self):
        """Initialize citation generator."""
        pass
    
    def generate_citations(
        self, 
        research_data: Optional[dict] = None,
        serp_data: Optional[dict] = None,
        keyword: str = ""
    ) -> list[dict]:
        """
        Generate citations from research and SERP data.
        
        Args:
            research_data: ResearchData dict with sources
            serp_data: CompleteSERPData dict
            keyword: The keyword these citations relate to
            
        Returns:
            List of citation dicts with APA/MLA/Chicago formats
        """
        citations = []
        citation_id = 1
        
        # Generate citations from research sources
        if research_data and research_data.get("sources"):
            for source in research_data["sources"]:
                citation = self._generate_research_citation(source, citation_id)
                if citation:
                    citations.append(citation)
                    citation_id += 1
        
        # Generate citations from SERP rankings
        if serp_data:
            # Featured snippet citation
            if serp_data.get("featured_snippet"):
                citation = self._generate_serp_citation(
                    serp_data["featured_snippet"], 
                    "featured_snippet",
                    citation_id
                )
                if citation:
                    citations.append(citation)
                    citation_id += 1
            
            # Top 3 organic results citations
            organic_results = serp_data.get("organic_results", [])
            for result in organic_results[:3]:  # Top 3 only
                citation = self._generate_serp_citation(
                    result,
                    "serp_ranking",
                    citation_id,
                    position=result.get("position")
                )
                if citation:
                    citations.append(citation)
                    citation_id += 1
            
            # PAA citations
            paa_questions = serp_data.get("paa_questions", [])
            for paa in paa_questions[:3]:  # Top 3 PAA
                citation = self._generate_serp_citation(
                    paa,
                    "paa",
                    citation_id
                )
                if citation:
                    citations.append(citation)
                    citation_id += 1
        
        return citations
    
    def _generate_research_citation(self, source: dict, citation_id: int) -> Optional[dict]:
        """Generate citation for a research source."""
        platform = source.get("platform", "").lower()
        url = source.get("url", "")
        author = source.get("source_author", "Anonymous")
        title = source.get("source_title", "")
        date = source.get("source_date", "")
        quote = source.get("quote", "")
        
        if not url:
            return None
        
        # Parse date
        date_str = self._parse_date(date)
        
        if platform == "reddit":
            return self._generate_reddit_citation(source, citation_id, author, title, date_str, url, quote)
        elif platform == "quora":
            return self._generate_quora_citation(source, citation_id, author, title, date_str, url, quote)
        elif platform == "forum":
            return self._generate_forum_citation(source, citation_id, author, title, date_str, url, quote)
        else:
            return self._generate_blog_citation(source, citation_id, author, title, date_str, url, quote)
    
    def _generate_reddit_citation(
        self, source: dict, citation_id: int, author: str, title: str, 
        date_str: str, url: str, quote: str
    ) -> dict:
        """Generate Reddit citation."""
        subreddit = source.get("subreddit", "Reddit")
        upvotes = source.get("upvotes")
        comments = source.get("comments_count")
        
        # APA: Author. (Year, Month Day). Title. Reddit. URL
        apa = f"{author}. ({date_str['year']}, {date_str['month']} {date_str['day']}). {title}. {subreddit}. {url}"
        
        # MLA: Author. "Title." Reddit, Day Month Year, URL
        mla = f'{author}. "{title}." {subreddit}, {date_str["day"]} {date_str["month"]} {date_str["year"]}, {url}'
        
        # Chicago: Author. "Title." Reddit, Month Day, Year. URL
        chicago = f'{author}. "{title}." {subreddit}, {date_str["month"]} {date_str["day"]}, {date_str["year"]}. {url}'
        
        engagement = ""
        if upvotes:
            engagement += f"{upvotes} upvotes"
        if comments:
            if engagement:
                engagement += ", "
            engagement += f"{comments} comments"
        
        return {
            "id": citation_id,
            "type": "research",
            "platform": "reddit",
            "source": subreddit,
            "author": author,
            "date": date_str.get("full", ""),
            "url": url,
            "text": quote[:200] + "..." if len(quote) > 200 else quote,
            "title": title,
            "engagement": engagement,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_quora_citation(
        self, source: dict, citation_id: int, author: str, title: str,
        date_str: str, url: str, quote: str
    ) -> dict:
        """Generate Quora citation."""
        views = source.get("views")
        
        # APA: Author. (Year, Month Day). Title. Quora. URL
        apa = f"{author}. ({date_str['year']}, {date_str['month']} {date_str['day']}). {title}. Quora. {url}"
        
        # MLA: Author. "Title." Quora, Day Month Year, URL
        mla = f'{author}. "{title}." Quora, {date_str["day"]} {date_str["month"]} {date_str["year"]}, {url}'
        
        # Chicago: Author. "Title." Quora, Month Day, Year. URL
        chicago = f'{author}. "{title}." Quora, {date_str["month"]} {date_str["day"]}, {date_str["year"]}. {url}'
        
        engagement = f"{views:,} views" if views else ""
        
        return {
            "id": citation_id,
            "type": "research",
            "platform": "quora",
            "source": "Quora",
            "author": author,
            "date": date_str.get("full", ""),
            "url": url,
            "text": quote[:200] + "..." if len(quote) > 200 else quote,
            "title": title,
            "engagement": engagement,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_forum_citation(
        self, source: dict, citation_id: int, author: str, title: str,
        date_str: str, url: str, quote: str
    ) -> dict:
        """Generate forum citation."""
        platform_name = source.get("topic_category", "Forum")
        
        # APA: Author. (Year, Month Day). Title. Platform Name. URL
        apa = f"{author}. ({date_str['year']}, {date_str['month']} {date_str['day']}). {title}. {platform_name}. {url}"
        
        # MLA: Author. "Title." Platform Name, Day Month Year, URL
        mla = f'{author}. "{title}." {platform_name}, {date_str["day"]} {date_str["month"]} {date_str["year"]}, {url}'
        
        # Chicago: Author. "Title." Platform Name, Month Day, Year. URL
        chicago = f'{author}. "{title}." {platform_name}, {date_str["month"]} {date_str["day"]}, {date_str["year"]}. {url}'
        
        return {
            "id": citation_id,
            "type": "research",
            "platform": "forum",
            "source": platform_name,
            "author": author,
            "date": date_str.get("full", ""),
            "url": url,
            "text": quote[:200] + "..." if len(quote) > 200 else quote,
            "title": title,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_blog_citation(
        self, source: dict, citation_id: int, author: str, title: str,
        date_str: str, url: str, quote: str
    ) -> dict:
        """Generate blog citation."""
        domain = self._extract_domain(url)
        
        # APA: Author. (Year, Month Day). Title. Domain. URL
        apa = f"{author}. ({date_str['year']}, {date_str['month']} {date_str['day']}). {title}. {domain}. {url}"
        
        # MLA: Author. "Title." Domain, Day Month Year, URL
        mla = f'{author}. "{title}." {domain}, {date_str["day"]} {date_str["month"]} {date_str["year"]}, {url}'
        
        # Chicago: Author. "Title." Domain, Month Day, Year. URL
        chicago = f'{author}. "{title}." {domain}, {date_str["month"]} {date_str["day"]}, {date_str["year"]}. {url}'
        
        return {
            "id": citation_id,
            "type": "research",
            "platform": "blog",
            "source": domain,
            "author": author or "Anonymous",
            "date": date_str.get("full", ""),
            "url": url,
            "text": quote[:200] + "..." if len(quote) > 200 else quote,
            "title": title,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_serp_citation(
        self, result: dict, citation_type: str, citation_id: int, position: Optional[int] = None
    ) -> Optional[dict]:
        """Generate citation for SERP result."""
        url = result.get("url") or result.get("source_url", "")
        title = result.get("title") or result.get("source_title", "")
        domain = result.get("domain") or result.get("source_domain", "")
        
        if not url:
            return None
        
        # Extract domain if not provided
        if not domain:
            domain = self._extract_domain(url)
        
        # Parse date
        date_str = self._parse_date(result.get("publish_date") or result.get("last_updated", ""))
        
        if citation_type == "featured_snippet":
            return self._generate_featured_snippet_citation(result, citation_id, title, domain, date_str, url)
        elif citation_type == "serp_ranking":
            return self._generate_ranking_citation(result, citation_id, title, domain, date_str, url, position)
        elif citation_type == "paa":
            return self._generate_paa_citation(result, citation_id, title, domain, date_str, url)
        return None
    
    def _generate_featured_snippet_citation(
        self, result: dict, citation_id: int, title: str, domain: str, date_str: dict, url: str
    ) -> dict:
        """Generate featured snippet citation."""
        snippet_type = result.get("type", "paragraph")
        content = result.get("content", "")
        
        # APA: Domain. (Year). Title. Retrieved from URL
        apa = f"{domain}. ({date_str['year']}). {title}. Retrieved from {url}"
        
        # MLA: Domain. "Title." Domain, Year, URL
        mla = f'{domain}. "{title}." {domain}, {date_str["year"]}, {url}'
        
        # Chicago: Domain. "Title." Domain, Year. URL
        chicago = f'{domain}. "{title}." {domain}, {date_str["year"]}. {url}'
        
        return {
            "id": citation_id,
            "type": "featured_snippet",
            "platform": "serp",
            "source": domain,
            "domain": domain,
            "url": url,
            "title": title,
            "snippet_type": snippet_type,
            "content": content[:200] + "..." if len(content) > 200 else content,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_ranking_citation(
        self, result: dict, citation_id: int, title: str, domain: str, date_str: dict, url: str, position: Optional[int]
    ) -> dict:
        """Generate SERP ranking citation."""
        # APA: Domain. (Year). Title. Retrieved from URL
        apa = f"{domain}. ({date_str['year']}). {title}. Retrieved from {url}"
        
        # MLA: Domain. "Title." Domain, Year, URL
        mla = f'{domain}. "{title}." {domain}, {date_str["year"]}, {url}'
        
        # Chicago: Domain. "Title." Domain, Year. URL
        chicago = f'{domain}. "{title}." {domain}, {date_str["year"]}. {url}'
        
        return {
            "id": citation_id,
            "type": "serp_ranking",
            "platform": "serp",
            "position": position,
            "source": domain,
            "domain": domain,
            "url": url,
            "title": title,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _generate_paa_citation(
        self, result: dict, citation_id: int, title: str, domain: str, date_str: dict, url: str
    ) -> dict:
        """Generate PAA citation."""
        question = result.get("question", "")
        answer = result.get("answer_snippet", "")
        
        # APA: Domain. (Year). Question. Retrieved from URL
        apa = f"{domain}. ({date_str['year']}). {question}. Retrieved from {url}"
        
        # MLA: Domain. "Question." Domain, Year, URL
        mla = f'{domain}. "{question}." {domain}, {date_str["year"]}, {url}'
        
        # Chicago: Domain. "Question." Domain, Year. URL
        chicago = f'{domain}. "{question}." {domain}, {date_str["year"]}. {url}'
        
        return {
            "id": citation_id,
            "type": "paa",
            "platform": "serp",
            "source": domain,
            "domain": domain,
            "url": url,
            "question": question,
            "answer": answer[:200] + "..." if len(answer) > 200 else answer,
            "format_apa": apa,
            "format_mla": mla,
            "format_chicago": chicago,
        }
    
    def _parse_date(self, date_str: str) -> dict:
        """Parse date string into components."""
        if not date_str:
            now = datetime.now()
            return {
                "year": str(now.year),
                "month": now.strftime("%B"),
                "day": str(now.day),
                "full": now.strftime("%Y-%m-%d"),
            }
        
        try:
            # Try ISO format: 2024-11-15T14:32:00Z
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(date_str)
            
            return {
                "year": str(dt.year),
                "month": dt.strftime("%B"),
                "day": str(dt.day),
                "full": dt.strftime("%Y-%m-%d"),
            }
        except (ValueError, AttributeError):
            # Fallback to current date
            now = datetime.now()
            return {
                "year": str(now.year),
                "month": now.strftime("%B"),
                "day": str(now.day),
                "full": now.strftime("%Y-%m-%d"),
            }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return "Unknown"
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain or "Unknown"
        except Exception:
            return "Unknown"

