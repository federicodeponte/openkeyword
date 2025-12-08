"""
Company Analysis Module for OpenKeywords

Pre-analyzes company website to extract rich context before keyword generation.
This ensures keywords are company-specific, not generic industry keywords.

Uses Gemini 3 Pro Preview with url_context + google_search for:
- Company description & industry
- Products & services (what they SELL)
- Pain points & customer problems
- Value propositions & differentiators  
- Competitors
- Target audience
- Use cases
- Brand voice & tone

This rich context feeds into the keyword generator for HYPER-SPECIFIC results.
"""

import os
import logging
import asyncio
import json
from typing import Optional

logger = logging.getLogger(__name__)

# Response schema for structured company analysis
COMPANY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "description": {"type": "string", "description": "2-3 sentences about what the company does"},
        "industry": {"type": "string", "description": "Industry category (e.g., EdTech, FinTech, SaaS)"},
        "target_audience": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Who are their customers?"
        },
        "products": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main products they SELL (2-5 items)"
        },
        "services": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Professional services they offer"
        },
        "pain_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Customer frustrations and problems"
        },
        "customer_problems": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Issues their solution addresses"
        },
        "use_cases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Real scenarios where product is used"
        },
        "value_propositions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key value they provide to customers"
        },
        "differentiators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What makes them unique vs competitors"
        },
        "key_features": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technical capabilities and features"
        },
        "solution_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Terms describing their approach/solution"
        },
        "competitors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 competitor names"
        },
        "brand_voice": {"type": "string", "description": "Communication style (formal/casual, technical/simple)"},
        "product_category": {"type": "string"},
        "primary_region": {"type": "string"}
    },
    "required": ["company_name", "description", "industry", "products"]
}


class CompanyAnalyzer:
    """Analyze company website to extract rich context for keyword generation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-pro-preview"
    ):
        """
        Initialize company analyzer.
        
        Args:
            api_key: Gemini API key (or set GEMINI_API_KEY env var)
            model: Gemini model to use
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required")
        
        # Use the google-genai SDK (same as ResearchEngine and GeminiSerpAnalyzer)
        try:
            from google import genai
            from google.genai import types
            
            self.genai = genai
            self.types = types
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = model
            logger.info(f"Company Analyzer initialized with URL context + Google Search (model={model})")
        except ImportError:
            raise ImportError(
                "google-genai SDK required for company analysis. "
                "Install with: pip install google-genai"
            )
    
    async def analyze(self, website_url: str) -> dict:
        """
        Analyze company website to extract rich context.
        
        Args:
            website_url: Company website URL
            
        Returns:
            Dictionary with company analysis:
            - company_name
            - description
            - industry
            - products (what they sell)
            - services
            - pain_points (customer frustrations)
            - customer_problems
            - use_cases
            - value_propositions
            - differentiators
            - key_features
            - solution_keywords
            - competitors
            - brand_voice
            - target_audience
            - product_category
            - primary_region
        """
        logger.info(f"Analyzing company website: {website_url}")
        
        # Get current date for context
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        
        prompt = f"""Today's date: {current_date}

Analyze the company at {website_url}

STEP 1: Read the website using URL context
- Use the URL context tool to read {website_url}
- Extract information directly from the homepage, about page, services/products pages
- Pay attention to what they actually SELL, their value proposition, target customers

STEP 2: Search Google for additional context
- Search: "{website_url} products services"
- Search: "{website_url} customers reviews pain points"
- Search: "{website_url} vs competitors"
- Find customer problems, use cases, differentiators

STEP 3: Provide comprehensive company analysis

Focus on extracting SPECIFIC information:
- What do they SELL? (products/services) - Use their actual product/service names
- What problems do they SOLVE? (pain points/customer problems)
- What makes them UNIQUE? (differentiators/value props)
- Who are their CUSTOMERS? (target audience)
- Who are their COMPETITORS?
- What is their BRAND VOICE? (formal/casual, technical/simple)
- What INDUSTRY are they in? (be specific!)

Be thorough and specific. Use real information from the website and search results.

Return JSON matching this schema:
{json.dumps(COMPANY_ANALYSIS_SCHEMA, indent=2)}"""

        try:
            # Use same setup as ResearchEngine: new SDK with Google Search
            # CRITICAL: Use response_schema to enforce structured output
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=self.types.GenerateContentConfig(
                    tools=[self.types.Tool(google_search=self.types.GoogleSearch())],
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=COMPANY_ANALYSIS_SCHEMA,
                ),
            )
            
            # Parse JSON response
            if not hasattr(response, 'text') or not response.text:
                raise ValueError("Empty response from Gemini")
            
            response_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(response_text)
            
            # Validate required fields
            if not analysis.get("company_name"):
                raise ValueError("Missing required field: company_name")
            if not analysis.get("industry"):
                raise ValueError("Missing required field: industry")
            if not analysis.get("products"):
                raise ValueError("Missing required field: products")
            
            logger.info(f"✅ Company analysis complete: {analysis.get('company_name', 'Unknown')}")
            logger.info(f"   Industry: {analysis.get('industry', 'Unknown')}")
            logger.info(f"   Products: {len(analysis.get('products', []))} found")
            logger.info(f"   Services: {len(analysis.get('services', []))} found")
            logger.info(f"   Pain points: {len(analysis.get('pain_points', []))} found")
            logger.info(f"   Competitors: {len(analysis.get('competitors', []))} found")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Company analysis failed: {e}")
            raise


async def analyze_company(website_url: str, api_key: Optional[str] = None) -> dict:
    """
    Convenience function to analyze a company website.
    
    Args:
        website_url: Company website URL
        api_key: Optional Gemini API key
        
    Returns:
        Company analysis dictionary
    """
    analyzer = CompanyAnalyzer(api_key=api_key)
    return await analyzer.analyze(website_url)
