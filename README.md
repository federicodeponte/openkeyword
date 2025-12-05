# 🔑 OpenKeywords

**AI-powered SEO keyword generation using Google Gemini + SE Ranking**

Generate high-quality, clustered SEO keywords for any business in any language.

## ✨ Features

- **AI Keyword Generation** - Google Gemini generates diverse, relevant keywords
- **Intent Classification** - Automatic classification (question, commercial, transactional, comparison, informational)
- **Company-Fit Scoring** - AI scores each keyword's relevance (0-100)
- **Semantic Clustering** - Groups keywords into topic clusters
- **Two-Stage Deduplication** - Fast token-based + AI semantic deduplication
- **SE Ranking Gap Analysis** - Find competitor keyword gaps (optional)
- **Any Language** - Dynamic language support, no hardcoded lists
- **AEO Optimized** - Prioritizes question keywords for Answer Engine Optimization

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
export GEMINI_API_KEY="your-gemini-api-key"
export SERANKING_API_KEY="your-seranking-key"  # Optional - for gap analysis
```

### CLI Usage

```bash
# Basic generation
openkeywords generate \
  --company "Acme Software" \
  --industry "B2B SaaS" \
  --services "project management,team collaboration" \
  --count 50

# With SE Ranking gap analysis (requires URL + API key)
openkeywords generate \
  --company "Acme Software" \
  --url "https://acme.com" \
  --count 50 \
  --with-gaps

# Specify language and region
openkeywords generate \
  --company "SCAILE Technologies" \
  --industry "AEO Marketing" \
  --language "german" \
  --region "de" \
  --count 30

# With competitors for gap analysis
openkeywords generate \
  --company "Acme" \
  --url "https://acme.com" \
  --competitors "competitor1.com,competitor2.com" \
  --with-gaps

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
        target_count=50,           # Keywords to return
        min_score=40,              # Minimum company-fit score
        enable_clustering=True,    # Group into clusters
        cluster_count=6,           # Target cluster count
        language="english",        # Any language name
        region="us",               # Country code
    )

    # Generate keywords
    result = await generator.generate(company, config)

    # Access results
    for kw in result.keywords[:10]:
        print(f"{kw.keyword} | {kw.intent} | Score: {kw.score} | Cluster: {kw.cluster_name}")

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
| `volume` | int | Search volume (from SE Ranking gap analysis) |
| `difficulty` | int | SEO difficulty (from SE Ranking gap analysis) |

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
│  1. SE RANKING GAP ANALYSIS (Optional)                      │
│     └─ Find AEO-optimized keywords competitors rank for     │
│                                                              │
│  2. AI GENERATION (Gemini)                                  │
│     └─ Generate diverse keywords with intent distribution   │
│                                                              │
│  3. FAST DEDUPLICATION                                      │
│     └─ Exact match + token signature grouping O(n)          │
│                                                              │
│  4. SCORING (Gemini)                                        │
│     └─ Score company fit (0-100) in parallel batches        │
│                                                              │
│  5. SEMANTIC DEDUPLICATION (Gemini)                         │
│     └─ Single prompt removes near-duplicates                │
│        "sign up X" vs "sign up for X" → keep best           │
│                                                              │
│  6. CLUSTERING (Gemini)                                     │
│     └─ Group into semantic topic clusters                   │
│                                                              │
│  7. FILTERING                                               │
│     └─ Apply min_score, limit to target_count               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

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
- [Google Gemini](https://ai.google.dev/)
- [SCAILE Technologies](https://scaile.tech)
