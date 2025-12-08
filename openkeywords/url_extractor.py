"""
URL extraction and meta tag fetching utilities.
Extracts real URLs from Vertex AI redirects and fetches meta tags.
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx

logger = logging.getLogger(__name__)


def extract_real_url_from_redirect(redirect_url: str) -> str:
    """
    Extract real URL from Vertex AI redirect URL.
    
    Vertex AI redirect URLs look like:
    https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQ...
    
    We try to extract the actual URL from the redirect or follow it.
    """
    if not redirect_url or not isinstance(redirect_url, str):
        return redirect_url
    
    # If it's already a real URL (not a redirect), return as-is
    if not redirect_url.startswith("https://vertexaisearch.cloud.google.com/grounding-api-redirect/"):
        return redirect_url
    
    # Try to extract URL from redirect (sometimes encoded in the path)
    # The redirect URL might contain the destination in query params or path
    try:
        parsed = urlparse(redirect_url)
        # Check query params
        query_params = parse_qs(parsed.query)
        if 'url' in query_params:
            return query_params['url'][0]
        if 'destination' in query_params:
            return query_params['destination'][0]
        
        # Sometimes the URL is base64 encoded in the path
        # We'll need to follow the redirect to get the real URL
        return redirect_url  # Will be resolved by following redirect
    except Exception as e:
        logger.debug(f"Failed to extract URL from redirect: {e}")
        return redirect_url


async def follow_redirect_to_real_url(redirect_url: str, timeout: float = 5.0) -> str:
    """
    Follow redirect to get the actual destination URL.
    
    Args:
        redirect_url: The redirect URL to follow
        timeout: Request timeout in seconds
        
    Returns:
        Final destination URL after following redirects
    """
    if not redirect_url or not isinstance(redirect_url, str):
        return redirect_url
    
    # If it's not a redirect URL, return as-is
    if not redirect_url.startswith("https://vertexaisearch.cloud.google.com/grounding-api-redirect/"):
        return redirect_url
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.head(redirect_url, allow_redirects=True)
            final_url = str(response.url)
            
            # If we got a real URL (not another redirect), return it
            if not final_url.startswith("https://vertexaisearch.cloud.google.com/"):
                logger.debug(f"Resolved redirect: {redirect_url[:50]}... -> {final_url[:80]}...")
                return final_url
            
            # If still a redirect, try GET request
            response = await client.get(redirect_url, allow_redirects=True)
            final_url = str(response.url)
            return final_url
            
    except Exception as e:
        logger.warning(f"Failed to follow redirect for {redirect_url[:50]}...: {e}")
        return redirect_url  # Return original if redirect fails


async def extract_meta_tags(url: str, timeout: float = 5.0) -> dict:
    """
    Fetch and extract meta tags from a URL.
    
    Extracts:
    - Open Graph tags (og:title, og:description, og:image, og:url)
    - Twitter Card tags (twitter:title, twitter:description, twitter:image)
    - Standard meta tags (title, description, keywords, author)
    - Canonical URL
    - Schema.org structured data
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Dict with meta tags
    """
    meta_tags = {
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "og_url": None,
        "og_type": None,
        "twitter_title": None,
        "twitter_description": None,
        "twitter_image": None,
        "twitter_card": None,
        "meta_title": None,
        "meta_description": None,
        "meta_keywords": None,
        "meta_author": None,
        "canonical_url": None,
        "schema_type": None,
    }
    
    if not url or not url.startswith("http"):
        return meta_tags
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; OpenKeywordsBot/1.0; +https://github.com/openkeywords)"
            })
            html = response.text
            
            # Extract Open Graph tags
            og_patterns = {
                "og_title": r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
                "og_description": r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
                "og_image": r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                "og_url": r'<meta\s+property=["\']og:url["\']\s+content=["\']([^"\']+)["\']',
                "og_type": r'<meta\s+property=["\']og:type["\']\s+content=["\']([^"\']+)["\']',
            }
            
            for key, pattern in og_patterns.items():
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    meta_tags[key] = match.group(1)
            
            # Extract Twitter Card tags
            twitter_patterns = {
                "twitter_title": r'<meta\s+name=["\']twitter:title["\']\s+content=["\']([^"\']+)["\']',
                "twitter_description": r'<meta\s+name=["\']twitter:description["\']\s+content=["\']([^"\']+)["\']',
                "twitter_image": r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
                "twitter_card": r'<meta\s+name=["\']twitter:card["\']\s+content=["\']([^"\']+)["\']',
            }
            
            for key, pattern in twitter_patterns.items():
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    meta_tags[key] = match.group(1)
            
            # Extract standard meta tags
            standard_patterns = {
                "meta_title": r'<title>([^<]+)</title>',
                "meta_description": r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
                "meta_keywords": r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']+)["\']',
                "meta_author": r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']',
            }
            
            for key, pattern in standard_patterns.items():
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    meta_tags[key] = match.group(1)
            
            # Extract canonical URL
            canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if canonical_match:
                meta_tags["canonical_url"] = canonical_match.group(1)
            
            # Extract Schema.org type
            schema_match = re.search(r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
            if schema_match:
                try:
                    import json
                    schema_data = json.loads(schema_match.group(1))
                    if isinstance(schema_data, dict) and "@type" in schema_data:
                        meta_tags["schema_type"] = schema_data["@type"]
                except:
                    pass
            
    except Exception as e:
        logger.debug(f"Failed to extract meta tags from {url[:50]}...: {e}")
    
    return meta_tags


async def resolve_urls_batch(urls: list[str], extract_meta: bool = True) -> dict[str, dict]:
    """
    Resolve multiple URLs in parallel and extract meta tags.
    
    Args:
        urls: List of URLs to resolve
        extract_meta: Whether to extract meta tags
        
    Returns:
        Dict mapping original URL to resolved URL and meta tags
    """
    results = {}
    
    async def resolve_one(url: str):
        try:
            # Resolve redirect
            real_url = await follow_redirect_to_real_url(url)
            
            # Extract meta tags if requested
            meta_tags = {}
            if extract_meta:
                meta_tags = await extract_meta_tags(real_url)
            
            return url, {
                "original_url": url,
                "resolved_url": real_url,
                "meta_tags": meta_tags,
            }
        except Exception as e:
            logger.warning(f"Failed to resolve {url[:50]}...: {e}")
            return url, {
                "original_url": url,
                "resolved_url": url,  # Fallback to original
                "meta_tags": {},
            }
    
    # Resolve in parallel (limit concurrency to avoid overwhelming servers)
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def resolve_with_semaphore(url: str):
        async with semaphore:
            return await resolve_one(url)
    
    tasks = [resolve_with_semaphore(url) for url in urls if url]
    resolved = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in resolved:
        if isinstance(result, Exception):
            logger.warning(f"URL resolution failed: {result}")
            continue
        original_url, data = result
        results[original_url] = data
    
    return results

