# 📖 Google Gemini Deep Research API Guide

> Complete guide to using Google Gemini API for deep research with source citations

## Overview

Google Gemini's API provides powerful deep research capabilities through:

1. **Google Search Grounding**: Real-time web search integration
2. **groundingMetadata**: Structured source citations
3. **JSON Schema Output**: Structured response format

## Getting Started

### 1. Get API Key

1. Go to [Google AI Studio](https://ai.google.dev/)
2. Click "Get API Key"
3. Create a new API key
4. Copy and save the key securely

### 2. Install SDK

```bash
pip install google-generativeai
```

### 3. Basic Usage

```python
import google.generativeai as genai

# Configure API key
genai.configure(api_key="YOUR_API_KEY")

# Create model with search grounding
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    tools=[{"google_search": {}}],  # Enable search
)

# Generate content
response = model.generate_content(
    "Research: Did Bitcoin reach $100,000 in December 2025?"
)

print(response.text)
```

## Search Grounding

### Enabling Search

```python
# Method 1: In model definition
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    tools=[{"google_search": {}}],
)

# Method 2: Per request
response = model.generate_content(
    "Your question here",
    tools=[{"google_search": {}}],
)
```

### Dynamic Search Retrieval

For more control over search behavior:

```python
from google.generativeai.types import DynamicRetrievalConfig

response = model.generate_content(
    "Your research question",
    tools=[{
        "google_search_retrieval": {
            "dynamic_retrieval_config": {
                "mode": "MODE_DYNAMIC",
                "dynamic_threshold": 0.3,  # Lower = more search
            }
        }
    }],
)
```

## Extracting Sources (groundingMetadata)

### Response Structure

```python
response = model.generate_content("Research question...")

# Access grounding metadata
candidate = response.candidates[0]

if hasattr(candidate, 'grounding_metadata'):
    metadata = candidate.grounding_metadata
    
    # 1. Grounding Chunks (Source URLs)
    for chunk in metadata.grounding_chunks:
        print(f"URL: {chunk.web.uri}")
        print(f"Title: {chunk.web.title}")
    
    # 2. Grounding Supports (Text-to-Source Mapping)
    for support in metadata.grounding_supports:
        print(f"Text segment: {support.segment.text}")
        print(f"Start: {support.segment.start_index}")
        print(f"End: {support.segment.end_index}")
        print(f"Source indices: {support.grounding_chunk_indices}")
```

### Complete Source Extraction

```python
def extract_sources(response) -> list[dict]:
    """Extract all sources from Gemini response."""
    sources = []
    
    if not hasattr(response, 'candidates'):
        return sources
    
    candidate = response.candidates[0]
    
    if not hasattr(candidate, 'grounding_metadata'):
        return sources
    
    metadata = candidate.grounding_metadata
    
    # Extract from grounding chunks
    if hasattr(metadata, 'grounding_chunks'):
        for i, chunk in enumerate(metadata.grounding_chunks):
            if hasattr(chunk, 'web'):
                sources.append({
                    'index': i,
                    'url': chunk.web.uri,
                    'title': chunk.web.title,
                })
    
    # Map text segments to sources
    if hasattr(metadata, 'grounding_supports'):
        for support in metadata.grounding_supports:
            segment_text = support.segment.text if hasattr(support.segment, 'text') else ""
            for idx in support.grounding_chunk_indices:
                if idx < len(sources):
                    if 'cited_text' not in sources[idx]:
                        sources[idx]['cited_text'] = []
                    sources[idx]['cited_text'].append(segment_text)
    
    return sources
```

### Example Output

```python
sources = extract_sources(response)

# Output:
[
    {
        'index': 0,
        'url': 'https://www.coinbase.com/price/bitcoin',
        'title': 'Bitcoin Price | BTC Price Index | Coinbase',
        'cited_text': ['Bitcoin reached $100,847.23']
    },
    {
        'index': 1,
        'url': 'https://www.reuters.com/technology/bitcoin-100000/',
        'title': 'Bitcoin tops $100,000 for first time - Reuters',
        'cited_text': ['Bitcoin crossed the $100,000 threshold']
    },
    # ... more sources
]
```

## Structured JSON Output

### Using JSON Schema

```python
from google.generativeai.types import GenerationConfig

# Define output schema
research_schema = {
    "type": "object",
    "properties": {
        "outcome": {
            "type": "string",
            "enum": ["YES", "NO", "UNDETERMINED"]
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
        },
        "reasoning": {
            "type": "string"
        },
        "key_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_url": {"type": "string"},
                    "source_title": {"type": "string"}
                }
            }
        }
    },
    "required": ["outcome", "confidence", "reasoning"]
}

response = model.generate_content(
    "Research: Did SpaceX land Starship successfully?",
    generation_config=GenerationConfig(
        response_mime_type="application/json",
        response_schema=research_schema,
    ),
    tools=[{"google_search": {}}],
)

import json
result = json.loads(response.text)
print(result)
```

### Example JSON Output

```json
{
    "outcome": "YES",
    "confidence": 92,
    "reasoning": "Multiple reliable sources confirm SpaceX successfully landed Starship on December 15, 2025...",
    "key_evidence": [
        {
            "claim": "Starship completed controlled landing at Boca Chica",
            "source_url": "https://www.spacex.com/updates",
            "source_title": "SpaceX - Updates"
        },
        {
            "claim": "FAA confirmed successful landing with no anomalies",
            "source_url": "https://www.faa.gov/space",
            "source_title": "FAA Space Transportation"
        }
    ]
}
```

## Optimizing for Deep Research

### Research-Focused Prompts

```python
DEEP_RESEARCH_PROMPT = """You are a Deep Research Agent for a prediction market oracle.

## QUESTION
{question}

## RESOLUTION CRITERIA
{criteria}

## RESEARCH INSTRUCTIONS

1. **Comprehensive Search**: Search for at least 50 diverse sources
2. **Source Diversity**: Include sources from these categories:
   - Official sources (.gov, company websites, press releases)
   - Major news outlets (Reuters, AP, Bloomberg, BBC)
   - Social media (verified accounts on Twitter/X, Reddit)
   - Domain-specific sources (industry publications)
   - Fact-checking sites (Snopes, PolitiFact)

3. **Evidence Analysis**:
   - Identify consensus across sources
   - Note any contradictions
   - Assess source reliability
   - Check recency of information

4. **Outcome Determination**:
   - YES: Event clearly occurred, supported by multiple reliable sources
   - NO: Event clearly did not occur, confirmed by reliable sources
   - UNDETERMINED: Insufficient or conflicting evidence

## OUTPUT REQUIREMENTS

Provide your research in JSON format:
{{
    "outcome": "YES" | "NO" | "UNDETERMINED",
    "confidence": 0-100,
    "reasoning": "Detailed analysis...",
    "key_findings": [
        {{
            "finding": "Description",
            "sources": ["url1", "url2"]
        }}
    ],
    "contradictions": [],
    "source_count": {{
        "official": 0,
        "news": 0,
        "social": 0,
        "domain": 0,
        "fact_check": 0
    }}
}}
"""
```

### Iterative Research

If first pass doesn't get enough sources:

```python
async def deep_research(question: str, min_sources: int = 50) -> dict:
    """Conduct deep research with minimum source requirements."""
    
    sources = []
    iterations = 0
    max_iterations = 3
    
    while len(sources) < min_sources and iterations < max_iterations:
        iterations += 1
        
        # Adjust prompt based on iteration
        if iterations == 1:
            prompt = f"Comprehensively research: {question}"
        else:
            prompt = f"""Continue researching: {question}
            
            You have found {len(sources)} sources so far.
            Find at least {min_sources - len(sources)} more sources.
            Focus on categories you haven't covered:
            {get_missing_categories(sources)}
            """
        
        response = await model.generate_content_async(
            prompt,
            tools=[{"google_search": {}}],
        )
        
        new_sources = extract_sources(response)
        
        # Deduplicate
        for source in new_sources:
            if source['url'] not in [s['url'] for s in sources]:
                sources.append(source)
    
    return {
        'sources': sources,
        'source_count': len(sources),
        'iterations': iterations,
    }
```

## Rate Limits and Best Practices

### Rate Limits

| Tier | RPM | RPD | TPM |
|------|-----|-----|-----|
| Free | 15 | 1,500 | 1M |
| Pay-as-you-go | 1,000 | 30,000 | 4M |

### Best Practices

1. **Use async for parallel requests**
   ```python
   results = await asyncio.gather(
       agent1.research(question),
       agent2.research(question),
       agent3.research(question),
   )
   ```

2. **Cache responses** to avoid duplicate API calls
   ```python
   from cachetools import TTLCache
   cache = TTLCache(maxsize=100, ttl=3600)
   ```

3. **Handle rate limits gracefully**
   ```python
   from tenacity import retry, wait_exponential
   
   @retry(wait=wait_exponential(min=1, max=60))
   async def research_with_retry(question):
       return await model.generate_content_async(question)
   ```

4. **Validate responses** before using
   ```python
   def validate_response(response):
       if not response.candidates:
           raise ValueError("No candidates in response")
       if not hasattr(response.candidates[0], 'grounding_metadata'):
           raise ValueError("No grounding metadata")
       return True
   ```

## Pricing

| Model | Input | Output |
|-------|-------|--------|
| gemini-2.0-flash-exp | $0.10 / 1M tokens | $0.40 / 1M tokens |
| gemini-1.5-pro | $1.25 / 1M tokens | $5.00 / 1M tokens |

*Search grounding may incur additional costs*

## Troubleshooting

### No grounding_metadata

```python
# Ensure search is enabled
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    tools=[{"google_search": {}}],  # This is required!
)
```

### Empty Sources

```python
# Check if search was actually performed
if hasattr(response.candidates[0], 'grounding_metadata'):
    metadata = response.candidates[0].grounding_metadata
    if hasattr(metadata, 'web_search_queries'):
        print(f"Queries used: {metadata.web_search_queries}")
```

### Rate Limited

```python
from google.api_core.exceptions import ResourceExhausted

try:
    response = model.generate_content(prompt)
except ResourceExhausted:
    print("Rate limited - waiting 60 seconds")
    await asyncio.sleep(60)
    response = model.generate_content(prompt)
```

## Next Steps

- See [ARCHITECTURE.md](./ARCHITECTURE.md) for full system design
- See `/agents/gemini_agent.py` for implementation
- See `/examples/` for usage examples
