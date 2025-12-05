# 🔑 OpenKeywords

**AI-powered SEO keyword generation using Google Gemini + SE Ranking + Deep Research + SERP Analysis**

Generate high-quality, clustered SEO keywords with AEO opportunity scoring for any business in any language.

## ✨ Features

- **🔍 Deep Research** - Find hyper-niche keywords from Reddit, Quora, forums using Google Search grounding
- **📊 SERP Analysis** - DataForSEO integration for featured snippet & PAA detection
- **📈 Volume Lookup** - Real search volumes from DataForSEO Keywords Data API
- **🎯 AEO Scoring** - Opportunity scores (0-100) based on featured snippets, PAA, competition
- **🤖 AI Keyword Generation** - Google Gemini generates diverse, relevant keywords
- **🏷️ Intent Classification** - Automatic classification (question, commercial, transactional, comparison, informational)
- **⭐ Company-Fit Scoring** - AI scores each keyword's relevance (0-100)
- **📦 Semantic Clustering** - Groups keywords into topic clusters
- **🔄 Two-Stage Deduplication** - Fast token-based + AI semantic deduplication
- **🔌 SE Ranking Gap Analysis** - Find competitor keyword gaps (optional)
- **🌍 Any Language** - Dynamic language support, no hardcoded lists
- **💡 AEO Optimized** - Prioritizes question keywords for Answer Engine Optimization

## 🚀 Quick Start

### Installation

```bash
pip install openkeywords
```

Or install from source:

```bash
git clone https://github.com/scaile/openkeywords.git
cd openkeywords
pip install -e .
```

### Set API Keys

```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"

# Optional - for enhanced features
export SERANKING_API_KEY="your-seranking-key"    # Gap analysis (--with-gaps)
export DATAFORSEO_LOGIN="your-email"             # SERP analysis (--with-serp)
export DATAFORSEO_PASSWORD="your-password"       # SERP analysis (--with-serp)
```

### CLI Usage

```bash
# Basic generation
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --services "project management,team collaboration" \
  --count 50

# 🔍 With Deep Research (Reddit, Quora, forums)
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --services "project management" \
  --count 50 \
  --with-research

# With SE Ranking gap analysis (requires URL + API key)
openkeywords generate \
  --company "Acme Software" \
  --url "https://acme.com" \
  --count 50 \
  --with-gaps

# 📊 With SERP Analysis (AEO opportunity scoring)
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --count 50 \
  --with-serp \
  --serp-sample 15

# 📈 With Volume Data (real search volumes from DataForSEO)
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --count 50 \
  --with-volume

# Full power: Research + SERP + Volume + Gap Analysis
openkeywords generate \
  --company "Acme Software" \
  --url "https://acme.com" \
  --industry "B2B SaaS" \
  --with-research \
  --with-serp \
  --with-volume \
  --with-gaps \
  --count 100

# Specify language and region
openkeywords generate \
  --company "SCAILE Technologies" \
  --industry "AEO Marketing" \
  --language "german" \
  --region "de" \
  --count 30

# Output to file
openkeywords generate \
  --company "Acme Software" \
  --count 50 \
  --output keywords.csv

# Check configuration
openkeywords check
```

### Python Usage

```python
import asyncio
from openkeywords import KeywordGenerator, CompanyInfo, GenerationConfig

async def generate_keywords():
    # Initialize generator
    generator = KeywordGenerator(
        gemini_api_key="your-key",  # or uses GEMINI_API_KEY env var
        seranking_api_key="your-key",  # optional - for gap analysis
    )

    # Define company
    company = CompanyInfo(
        name="Acme Software",
        url="https://acme.com",  # Required for gap analysis
        industry="B2B SaaS",
        services=["project management", "team collaboration"],
        products=["Acme Pro", "Acme Teams"],
        target_audience="small businesses",
        target_location="United States",
        competitors=["competitor1.com", "competitor2.com"],  # Optional
    )

    # Configure generation
    config = GenerationConfig(
        target_count=50,             # Keywords to return
        min_score=40,                # Minimum company-fit score
        enable_clustering=True,      # Group into clusters
        cluster_count=6,             # Target cluster count
        language="english",          # Any language name
        region="us",                 # Country code
        enable_research=True,        # 🔍 Enable deep research (Reddit, Quora, forums)
        enable_serp_analysis=True,   # 📊 Enable SERP analysis (featured snippets, PAA)
        serp_sample_size=15,         # How many keywords to analyze for SERP features
        enable_volume_lookup=True,   # 📈 Get real search volumes from DataForSEO
    )

    # Generate keywords
    result = await generator.generate(company, config)

    # Access results
    for kw in result.keywords[:10]:
        print(f"{kw.keyword} | {kw.intent} | Score: {kw.score} | Source: {kw.source}")

    # Export
    result.to_csv("keywords.csv")
    result.to_json("keywords.json")

    # Statistics
    print(f"Total: {result.statistics.total}")
    print(f"Avg Score: {result.statistics.avg_score:.1f}")
    print(f"Intent breakdown: {result.statistics.intent_breakdown}")

# Run
asyncio.run(generate_keywords())
```

## 📊 Output Format

### Keyword Object

| Field | Type | Description |
|-------|------|-------------|
| `keyword` | str | The keyword text |
| `intent` | str | `question`, `commercial`, `transactional`, `comparison`, `informational` |
| `score` | int | Company-fit score (0-100) |
| `cluster_name` | str | Semantic cluster grouping |
| `is_question` | bool | Is this a question-based keyword? |
| `source` | str | Where keyword came from: `ai_generated`, `research_reddit`, `research_quora`, `research_niche`, `gap_analysis`, `serp_paa` |
| `volume` | int | Monthly search volume (from DataForSEO --with-volume or SE Ranking --with-gaps) |
| `difficulty` | int | Keyword difficulty 0-100 (from DataForSEO or SE Ranking) |
| `aeo_opportunity` | int | AEO opportunity score 0-100 (from SERP analysis) |
| `has_featured_snippet` | bool | SERP has featured snippet (from SERP analysis) |
| `has_paa` | bool | SERP has People Also Ask (from SERP analysis) |
| `serp_analyzed` | bool | Whether SERP was analyzed for this keyword |

### Example Output

```json
{
  "keywords": [
    {
      "keyword": "best project management software for small teams",
      "intent": "commercial",
      "score": 92,
      "cluster_name": "Product Comparison",
      "is_question": false,
      "volume": 1200,
      "difficulty": 45
    },
    {
      "keyword": "how to improve team collaboration remotely",
      "intent": "question",
      "score": 85,
      "cluster_name": "How-To Guides",
      "is_question": true,
      "volume": 890,
      "difficulty": 32
    }
  ],
  "clusters": [
    {"name": "Product Comparison", "count": 12},
    {"name": "How-To Guides", "count": 8}
  ],
  "statistics": {
    "total": 50,
    "avg_score": 71.4,
    "intent_breakdown": {
      "question": 15,
      "commercial": 12,
      "transactional": 8,
      "comparison": 5,
      "informational": 10
    },
    "duplicate_count": 23
  }
}
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenKeywords Pipeline                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 🔍 DEEP RESEARCH (Optional - enable_research=True)      │
│     └─ Google Search grounding finds real user keywords     │
│        • Reddit discussions → pain points, questions        │
│        • Quora + PAA → real questions people ask            │
│        • Forums → niche terminology, use cases              │
│                                                              │
│  2. SE RANKING GAP ANALYSIS (Optional)                      │
│     └─ Find AEO-optimized keywords competitors rank for     │
│                                                              │
│  3. AI GENERATION (Gemini)                                  │
│     └─ Generate diverse keywords with intent distribution   │
│                                                              │
│  4. FAST DEDUPLICATION                                      │
│     └─ Exact match + token signature grouping O(n)          │
│                                                              │
│  5. SCORING (Gemini)                                        │
│     └─ Score company fit (0-100) in parallel batches        │
│                                                              │
│  6. SEMANTIC DEDUPLICATION (Gemini)                         │
│     └─ Single prompt removes near-duplicates                │
│        "sign up X" vs "sign up for X" → keep best           │
│                                                              │
│  7. CLUSTERING (Gemini)                                     │
│     └─ Group into semantic topic clusters                   │
│                                                              │
│  8. FILTERING                                               │
│     └─ Apply min_score, limit to target_count               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔍 Deep Research

Deep Research uses **Google Search grounding** to find hyper-niche keywords from real user discussions.

**What it searches:**
- **Reddit** - Real user pain points, questions, and terminology
- **Quora + PAA** - Actual questions people ask (People Also Ask)
- **Forums & Communities** - Niche industry terms and use cases

**Why it matters:**
- Finds keywords AI alone would **never generate**
- Discovers the **exact language** your audience uses
- Uncovers **long-tail, low-competition** opportunities
- Perfect for AEO (Answer Engine Optimization)

**Example keywords found by Deep Research:**
- "How do I make my content stand out to AI?" (from Reddit)
- "AI-driven content optimization for zero-click answers" (niche terminology)
- "why does Google ignore my structured data" (real user frustration)

```python
# Enable deep research
config = GenerationConfig(
    target_count=50,
    enable_research=True,  # 🔍 Enables Reddit, Quora, forum search
)

result = await generator.generate(company, config)

# Check keyword sources
for kw in result.keywords:
    print(f"{kw.keyword} | Source: {kw.source}")
    # Sources: research_reddit, research_quora, research_niche, ai_generated
```

**Note:** Deep Research requires the `google-genai` SDK and uses Gemini's Google Search tool.

## 🔌 SE Ranking Gap Analysis

SE Ranking provides competitor keyword gap analysis to find AEO-optimized opportunities.

**What it does:**
- Finds keywords your competitors rank for but you don't
- Filters for AEO potential (question intent, low difficulty, featured snippets)
- Provides real search volume and difficulty metrics

**AEO Filtering Criteria:**
- Volume: 100-5,000 (sweet spot for AI citations)
- Difficulty: ≤35 (achievable rankings)
- Word count: ≥3 (long-tail focus)
- Intent: Prioritizes questions and informational queries

```python
# Enable gap analysis
generator = KeywordGenerator(
    gemini_api_key="...",
    seranking_api_key="your-seranking-key",
)

# Generate with gap analysis (requires URL)
result = await generator.generate(
    CompanyInfo(
        name="Acme",
        url="https://acme.com",  # Required!
        competitors=["competitor1.com", "competitor2.com"],  # Optional
    ),
    GenerationConfig(target_count=50),
)
```

**Note:** Without SE Ranking, `volume` and `difficulty` will be `0` (AI-only generation still works perfectly).

## 📊 SERP Analysis (DataForSEO)

SERP Analysis provides **agency-level AEO opportunity scoring** using the DataForSEO API.

**What it detects:**
- **Featured Snippets** - Keywords with snippets are prime AEO targets
- **People Also Ask (PAA)** - Indicates Google wants Q&A content
- **Related Searches** - Bonus keyword discovery
- **Competition Level** - Who ranks in top 5 (big players vs niche sites)

**AEO Opportunity Scoring (0-100):**

| Factor | Score Impact |
|--------|--------------|
| Has Featured Snippet | +25 points |
| Has PAA Section | +15 points |
| Rich PAA (4+ questions) | +5 points |
| Question keyword | +10 points |
| No big players in top 5 | +10 points |
| High competition (3+ big sites) | -15 points |

**Usage:**

```bash
# Enable SERP analysis
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --with-serp \
  --serp-sample 15 \  # Analyze top 15 keywords
  --output keywords.csv
```

**Python:**

```python
from openkeywords import SerpAnalyzer, analyze_for_aeo

# Quick analysis
analyses, bonus_keywords = await analyze_for_aeo(
    ["what is SEO", "best SEO tools"],
    country="us",
)

for kw, analysis in analyses.items():
    f = analysis.features
    print(f"{kw}: AEO={f.aeo_opportunity} FS={f.has_featured_snippet} PAA={f.has_paa}")

# Or use the analyzer directly
analyzer = SerpAnalyzer(
    dataforseo_login="your-email",
    dataforseo_password="your-password",
)
analyses, bonus = await analyzer.analyze_keywords(keywords)
```

**Cost:** $0.50 per 1,000 queries ($0.0005 per keyword)

**Note:** Without DataForSEO credentials, SERP analysis is skipped but keyword generation works normally.

## ⚙️ Configuration

### GenerationConfig Options

| Option | Default | Description |
|--------|---------|-------------|
| `target_count` | 50 | Number of keywords to return |
| `min_score` | 40 | Minimum company-fit score (0-100) |
| `enable_clustering` | True | Group keywords into clusters |
| `cluster_count` | 6 | Target number of clusters |
| `language` | "english" | Target language (any language) |
| `region` | "us" | Target region (country code) |
| `enable_research` | False | 🔍 Enable deep research (Reddit, Quora, forums) |
| `enable_serp_analysis` | False | 📊 Enable SERP analysis for AEO scoring |
| `serp_sample_size` | 15 | Number of top keywords to analyze for SERP features |
| `enable_volume_lookup` | False | 📈 Get real search volumes from DataForSEO |

### Intent Distribution

The generator aims for a balanced distribution optimized for AEO:

| Intent | Target | Description |
|--------|--------|-------------|
| **Question** | 25% | AEO-optimized (how, what, why, when) |
| **Commercial** | 25% | Best, top, review, pricing |
| **Transactional** | 15% | Buy, sign up, get quote |
| **Comparison** | 10% | vs, alternative, difference |
| **Informational** | 25% | Guides, tips, benefits |

### Word Length Distribution

| Length | Target | Example |
|--------|--------|---------|
| Short (2-3 words) | 20% | "project management" |
| Medium (4-5 words) | 50% | "best project management software" |
| Long (6-7 words) | 30% | "how to choose project management tool" |

## 🌍 Multi-Language Support

OpenKeywords supports **any language** without hardcoded lists:

```bash
# German keywords for German market
openkeywords generate \
  --company "SCAILE Technologies" \
  --language "german" \
  --region "de"

# Spanish keywords for Mexico
openkeywords generate \
  --company "Acme Mexico" \
  --language "spanish" \
  --region "mx"

# Japanese keywords
openkeywords generate \
  --company "株式会社アクメ" \
  --language "japanese" \
  --region "jp"
```

The AI dynamically adapts prompts for question words, intent patterns, and cultural context.

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions welcome! Please submit issues and pull requests.

## 🔗 Links

- [SE Ranking API](https://seranking.com/api-documentation.html)
- [DataForSEO API](https://dataforseo.com/apis/serp-api)
- [Google Gemini](https://ai.google.dev/)
- [SCAILE Technologies](https://scaile.tech)
