# 🏗️ Prediction Market Oracle Architecture

> Technical architecture of the 1024 Prediction Market Multi-Agent Oracle  
> AI-Powered Market Resolution with Full Source Traceability  
> Powered by Google Gemini Deep Research API

## Overview

This oracle system resolves **1024 Prediction Market** questions using AI-powered research. It is built on **Google Gemini's Deep Research API** with the `groundingMetadata` feature that provides full source citations.

### Prediction Market Integration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    1024 Prediction Market Settlement Flow                    │
│                                                                              │
│   1. Market Created                                                          │
│      "Will BTC reach $100k by Dec 2025?"                                    │
│                    │                                                         │
│                    ▼                                                         │
│   2. Market Active (Trading Period)                                          │
│                    │                                                         │
│                    ▼                                                         │
│   3. Settlement Triggered ─────────────────────────────────────────────┐    │
│                    │                                                   │    │
│                    ▼                                                   │    │
│   ┌────────────────────────────────────────────────────────────────┐  │    │
│   │              Multi-Agent Deep Research Oracle                   │  │    │
│   │                                                                 │  │    │
│   │   POST /prediction/oracle/resolve                               │  │    │
│   │   { "market_id": 123 }                                         │  │    │
│   │                                                                 │  │    │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐                     │  │    │
│   │   │ Agent A  │  │ Agent B  │  │ Agent C  │                     │  │    │
│   │   │ Gemini   │  │ Gemini   │  │ Gemini   │                     │  │    │
│   │   │ 52 src   │  │ 48 src   │  │ 55 src   │                     │  │    │
│   │   │ YES 85%  │  │ YES 82%  │  │ YES 88%  │                     │  │    │
│   │   └──────────┘  └──────────┘  └──────────┘                     │  │    │
│   │                       │                                         │  │    │
│   │                       ▼                                         │  │    │
│   │              Consensus: YES (100%)                              │  │    │
│   │              Sources: 155 unique                                │  │    │
│   │              IPFS: Qm...xyz                                     │  │    │
│   └────────────────────────────────────────────────────────────────┘  │    │
│                    │                                                   │    │
│                    ▼                                                   │    │
│   4. Result Proposed to Chain ◄───────────────────────────────────────┘    │
│      ProposeResult { market: 123, outcome: YES, ipfs: "Qm..." }             │
│                    │                                                         │
│                    ▼                                                         │
│   5. Challenge Window (24h)                                                  │
│      - Anyone can verify sources via IPFS                                    │
│      - Anyone can challenge with bond                                        │
│                    │                                                         │
│                    ▼                                                         │
│   6. FinalizeResult                                                          │
│                    │                                                         │
│                    ▼                                                         │
│   7. Users Claim Winnings                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

Multiple independent agents research the same question and must reach consensus.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              System Layers                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Application Layer: Prediction Market Integration                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ↕                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  API Layer: REST / WebSocket / CLI                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ↕                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Core Layer                                                          │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │    │
│  │  │ Agent Manager │  │   Consensus   │  │    Storage    │            │    │
│  │  │               │  │    Engine     │  │   (IPFS)      │            │    │
│  │  └───────────────┘  └───────────────┘  └───────────────┘            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ↕                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  AI Provider Layer                                                   │    │
│  │  ┌───────────────────────────────────────────────────────────────┐  │    │
│  │  │  Google Gemini API (Primary)                                   │  │    │
│  │  │  - gemini-2.0-flash-exp                                        │  │    │
│  │  │  - Google Search grounding                                     │  │    │
│  │  │  - groundingMetadata for citations                             │  │    │
│  │  └───────────────────────────────────────────────────────────────┘  │    │
│  │  ┌───────────────────────────────────────────────────────────────┐  │    │
│  │  │  OpenAI (Optional, for diversity)                              │  │    │
│  │  │  - o3-deep-research (if available)                             │  │    │
│  │  └───────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    ↕                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Blockchain Layer: Solana Prediction Market Program                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Gemini Deep Research Agent

### Why Gemini?

| Feature | Gemini | OpenAI | Perplexity |
|---------|--------|--------|------------|
| **Deep Research Mode** | ✅ Native | ⚠️ Limited API | ❌ No |
| **Source Citations** | ✅ `groundingMetadata` | ✅ `annotations` | ✅ Basic |
| **Configurable Sources** | ✅ Yes | ⚠️ Limited | ❌ No |
| **JSON Schema Output** | ✅ Yes | ✅ Yes | ❌ No |
| **API Availability** | ✅ Open | ⚠️ Restricted | ✅ Open |
| **Cost** | 💰 Low | 💰💰💰 High | 💰💰 Medium |

### Gemini API Integration

```python
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

class GeminiDeepResearchAgent:
    """
    Deep Research Agent powered by Google Gemini API.
    
    Uses Google Search grounding to collect 50+ sources
    and returns structured results with full citations.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        min_sources: int = 50,
    ):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            tools=[{"google_search": {}}],  # Enable search grounding
        )
        self.min_sources = min_sources
    
    async def research(
        self,
        question: str,
        resolution_criteria: str,
    ) -> AgentResult:
        """
        Conduct deep research on a prediction market question.
        """
        prompt = self._build_research_prompt(question, resolution_criteria)
        
        response = await self.model.generate_content_async(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.1,  # Low temperature for factual research
                max_output_tokens=8192,
            ),
        )
        
        # Extract grounding metadata (sources)
        sources = self._extract_sources(response)
        
        # Validate minimum sources
        if len(sources) < self.min_sources:
            # Request more sources
            sources = await self._expand_research(question, sources)
        
        # Analyze and determine outcome
        outcome, confidence, reasoning = self._analyze_response(response)
        
        return AgentResult(
            agent_id=self.agent_id,
            model=self.model_name,
            outcome=outcome,
            confidence=confidence,
            reasoning=reasoning,
            sources=sources,
        )
    
    def _extract_sources(self, response) -> list[ResearchSource]:
        """
        Extract sources from Gemini's groundingMetadata.
        
        The response includes:
        - groundingMetadata.groundingChunks: List of source URLs
        - groundingMetadata.groundingSupports: Maps text to sources
        """
        sources = []
        
        if not hasattr(response, 'candidates'):
            return sources
        
        candidate = response.candidates[0]
        
        if hasattr(candidate, 'grounding_metadata'):
            metadata = candidate.grounding_metadata
            
            # Extract grounding chunks (sources)
            for chunk in metadata.grounding_chunks:
                if hasattr(chunk, 'web'):
                    sources.append(ResearchSource(
                        url=chunk.web.uri,
                        title=chunk.web.title,
                        category=self._categorize_url(chunk.web.uri),
                        relevance_score=0.8,  # Default, can be refined
                        credibility_score=self._calculate_credibility(chunk.web.uri),
                    ))
        
        return sources
    
    def _categorize_url(self, url: str) -> str:
        """Categorize a URL into source category."""
        domain = urlparse(url).netloc.lower()
        
        # Official sources
        if any(tld in domain for tld in ['.gov', '.edu']):
            return 'official'
        
        # News sources
        news_domains = ['reuters.com', 'apnews.com', 'bbc.com', 'bloomberg.com', 
                       'cnn.com', 'nytimes.com', 'wsj.com', 'theguardian.com']
        if any(news in domain for news in news_domains):
            return 'news'
        
        # Social sources
        social_domains = ['twitter.com', 'x.com', 'reddit.com', 'facebook.com']
        if any(social in domain for social in social_domains):
            return 'social'
        
        # Fact-check sources
        factcheck_domains = ['snopes.com', 'politifact.com', 'factcheck.org']
        if any(fc in domain for fc in factcheck_domains):
            return 'fact_check'
        
        # Default to domain-specific
        return 'domain_specific'
```

### Research Prompt Engineering

```python
def _build_research_prompt(self, question: str, criteria: str) -> str:
    """Build the research prompt for Gemini."""
    return f"""You are a Deep Research Agent for a prediction market oracle.
Your task is to comprehensively research whether an event has occurred.

## QUESTION
{question}

## RESOLUTION CRITERIA
{criteria}

## INSTRUCTIONS

1. **Search Comprehensively**: Use Google Search to find at least 50 diverse sources
2. **Source Categories**: Include sources from ALL of these categories:
   - Official sources (government, company websites, press releases)
   - News sources (Reuters, AP, Bloomberg, BBC, etc.)
   - Social media (verified Twitter/X accounts, Reddit)
   - Domain-specific sources (relevant industry sites)
   - Fact-checking sites (Snopes, PolitiFact)

3. **Analyze Evidence**: 
   - What do official sources say?
   - What does news coverage report?
   - Is there consensus across sources?
   - Are there any contradictions?

4. **Determine Outcome**:
   - YES: The event clearly occurred based on evidence
   - NO: The event clearly did not occur based on evidence
   - UNDETERMINED: Insufficient or conflicting evidence

5. **Provide Your Analysis**:
   - Start with your conclusion: YES, NO, or UNDETERMINED
   - State your confidence level (0-100%)
   - Explain your reasoning with specific citations
   - Note any caveats or conflicting information

## OUTPUT FORMAT

OUTCOME: [YES/NO/UNDETERMINED]
CONFIDENCE: [0-100]%

REASONING:
[Your detailed analysis with inline citations to sources]

KEY SOURCES:
1. [Source title] - [URL] - [Key finding]
2. [Source title] - [URL] - [Key finding]
...
"""
```

### Source Validation

```python
class SourceValidator:
    """Validates that research meets minimum requirements."""
    
    CATEGORY_REQUIREMENTS = {
        'official': 5,
        'news': 15,
        'social': 10,
        'domain_specific': 10,
        'fact_check': 3,
    }
    
    def validate(self, sources: list[ResearchSource]) -> ValidationResult:
        """Validate sources meet requirements."""
        
        # Count by category
        categories = {}
        for source in sources:
            cat = source.category
            categories[cat] = categories.get(cat, 0) + 1
        
        # Check total
        total_valid = len(sources) >= 50
        
        # Check categories
        category_valid = len(categories) >= 5
        
        # Check category minimums
        category_checks = {}
        for cat, min_count in self.CATEGORY_REQUIREMENTS.items():
            actual = categories.get(cat, 0)
            category_checks[cat] = {
                'required': min_count,
                'actual': actual,
                'valid': actual >= min_count,
            }
        
        return ValidationResult(
            is_valid=total_valid and category_valid,
            total_sources=len(sources),
            categories=categories,
            category_checks=category_checks,
        )
```

---

## 2. Multi-Agent Architecture

### Why Multiple Agents?

Using multiple independent agents provides:

1. **Redundancy**: One agent failure doesn't break the system
2. **Cross-Verification**: Different perspectives catch errors
3. **Confidence**: Agreement increases trust in results
4. **Manipulation Resistance**: Harder to fool multiple agents

### Agent Strategies

Each agent uses a different search strategy to ensure diverse source collection:

```python
class SearchStrategy(Enum):
    COMPREHENSIVE = "comprehensive"  # Broad search, many queries
    FOCUSED = "focused"              # Deep dive on key terms
    DIVERSE = "diverse"              # Maximize source variety
    SKEPTICAL = "skeptical"          # Look for counterarguments

class AgentConfig:
    """Configuration for each agent."""
    
    STRATEGIES = {
        SearchStrategy.COMPREHENSIVE: {
            "num_queries": 20,
            "depth": "deep",
            "follow_links": True,
        },
        SearchStrategy.FOCUSED: {
            "num_queries": 10,
            "depth": "very_deep", 
            "focus_on_primary": True,
        },
        SearchStrategy.DIVERSE: {
            "num_queries": 15,
            "depth": "medium",
            "maximize_domains": True,
        },
        SearchStrategy.SKEPTICAL: {
            "num_queries": 15,
            "depth": "deep",
            "include_counterarguments": True,
        },
    }
```

### Agent Isolation

Agents must be independent - no communication during research:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent Isolation Model                                │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Oracle Request                                  │  │
│  │  question: "Did X happen?"                                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│              ┌─────────────────────┼─────────────────────┐                 │
│              │                     │                     │                 │
│              ↓                     ↓                     ↓                 │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐        │
│  │   Container A     │ │   Container B     │ │   Container C     │        │
│  │   ─────────────   │ │   ─────────────   │ │   ─────────────   │        │
│  │   Agent A         │ │   Agent B         │ │   Agent C         │        │
│  │   (isolated)      │ │   (isolated)      │ │   (isolated)      │        │
│  │                   │ │                   │ │                   │        │
│  │   ❌ No comms     │ │   ❌ No comms     │ │   ❌ No comms     │        │
│  │   ❌ No shared    │ │   ❌ No shared    │ │   ❌ No shared    │        │
│  │      state        │ │      state        │ │      state        │        │
│  │                   │ │                   │ │                   │        │
│  │   ✅ Own API key  │ │   ✅ Own API key  │ │   ✅ Own API key  │        │
│  │   ✅ Own search   │ │   ✅ Own search   │ │   ✅ Own search   │        │
│  │                   │ │                   │ │                   │        │
│  └─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘        │
│            │                     │                     │                   │
│            │ Result A            │ Result B            │ Result C          │
│            │                     │                     │                   │
│            └─────────────────────┼─────────────────────┘                   │
│                                  ↓                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Consensus Engine                                   │  │
│  │  (First point where results are combined)                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Consensus Engine

### Algorithm

```python
class ConsensusEngine:
    """
    Byzantine Fault Tolerant consensus for oracle results.
    
    Requires 2/3+ supermajority for valid consensus.
    """
    
    def __init__(
        self,
        threshold: float = 0.67,
        min_confidence: float = 0.5,
        min_agents: int = 3,
    ):
        self.threshold = threshold
        self.min_confidence = min_confidence
        self.min_agents = min_agents
    
    def calculate_consensus(
        self,
        results: list[AgentResult],
    ) -> ConsensusResult:
        """Calculate consensus from agent results."""
        
        # Validate minimum agents
        if len(results) < self.min_agents:
            return ConsensusResult(
                outcome="INVALID",
                reason=f"Need {self.min_agents}+ agents, got {len(results)}",
            )
        
        # Validate each agent has enough sources
        for result in results:
            if len(result.sources) < 50:
                return ConsensusResult(
                    outcome="INVALID",
                    reason=f"Agent {result.agent_id} has only {len(result.sources)} sources",
                )
        
        # Group by outcome
        votes = {"YES": [], "NO": [], "UNDETERMINED": []}
        for result in results:
            if result.outcome in votes:
                votes[result.outcome].append(result)
        
        # Calculate weighted scores
        scores = {}
        for outcome, voters in votes.items():
            if voters:
                # Weight = confidence × source_quality
                score = sum(
                    r.confidence * self._source_quality_score(r.sources)
                    for r in voters
                )
                scores[outcome] = {
                    "count": len(voters),
                    "ratio": len(voters) / len(results),
                    "weighted_score": score,
                }
        
        # Find winner
        winner = max(scores.keys(), key=lambda k: scores[k]["weighted_score"])
        winner_ratio = scores[winner]["ratio"]
        
        # Check threshold
        if winner_ratio >= self.threshold:
            winning_results = votes[winner]
            merged_sources = self._merge_sources(winning_results)
            avg_confidence = sum(r.confidence for r in winning_results) / len(winning_results)
            
            return ConsensusResult(
                outcome=winner,
                confidence=avg_confidence,
                agreement_ratio=winner_ratio,
                sources=merged_sources,
                agent_results=results,
                requires_human_review=False,
            )
        else:
            return ConsensusResult(
                outcome="UNDETERMINED",
                confidence=0,
                agreement_ratio=winner_ratio,
                requires_human_review=True,
                disagreement_analysis=self._analyze_disagreement(results),
            )
    
    def _merge_sources(
        self,
        results: list[AgentResult],
    ) -> list[ResearchSource]:
        """Merge and deduplicate sources from all agents."""
        seen_urls = set()
        merged = []
        
        for result in results:
            for source in result.sources:
                if source.url not in seen_urls:
                    merged.append(source)
                    seen_urls.add(source.url)
        
        # Sort by relevance
        return sorted(merged, key=lambda s: s.relevance_score, reverse=True)
    
    def _source_quality_score(self, sources: list[ResearchSource]) -> float:
        """Calculate quality score for sources."""
        if not sources:
            return 0
        
        # Average credibility
        avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
        
        # Category diversity (0-1 based on coverage of 5 categories)
        categories = set(s.category for s in sources)
        diversity = min(len(categories) / 5, 1.0)
        
        # Source count factor
        count_factor = min(len(sources) / 50, 1.0)
        
        return avg_credibility * 0.4 + diversity * 0.3 + count_factor * 0.3
```

---

## 4. IPFS Storage

### Data Structure

```python
@dataclass
class IPFSResearchData:
    """Complete research data stored on IPFS."""
    
    version: str = "1.0.0"
    
    # Request
    market_id: int
    question: str
    resolution_criteria: str
    research_timestamp: str
    
    # Agent Results
    agents: list[AgentResultData]
    
    # Consensus
    consensus: ConsensusData
    
    # Merged Sources
    merged_sources: list[SourceData]
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

class IPFSClient:
    """Client for storing research data on IPFS."""
    
    async def store(self, data: IPFSResearchData) -> str:
        """Store data on IPFS, return CID."""
        json_data = data.to_json()
        
        # Upload to web3.storage or similar
        cid = await self.upload(json_data)
        
        return cid
    
    async def retrieve(self, cid: str) -> IPFSResearchData:
        """Retrieve data from IPFS by CID."""
        json_data = await self.download(cid)
        return IPFSResearchData(**json.loads(json_data))
```

---

## 5. Blockchain Integration

### Solana Program

```rust
// programs/oracle/src/lib.rs

use anchor_lang::prelude::*;

declare_id!("Oracle1024xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");

#[program]
pub mod multi_agent_oracle {
    use super::*;
    
    /// Submit oracle result from multi-agent consensus
    pub fn submit_result(
        ctx: Context<SubmitResult>,
        market_id: u64,
        outcome: u8,              // 0=NO, 1=YES, 2=UNDETERMINED
        confidence: u16,          // 0-10000 (0-100.00%)
        ipfs_cid: String,         // IPFS CID for full research
        agent_count: u8,          // Number of agents that participated
        source_count: u16,        // Total unique sources
        agreement_ratio: u16,     // 0-10000 (0-100.00%)
    ) -> Result<()> {
        require!(agent_count >= 3, OracleError::InsufficientAgents);
        require!(agreement_ratio >= 6700, OracleError::InsufficientConsensus);
        require!(source_count >= 50, OracleError::InsufficientSources);
        
        let result = &mut ctx.accounts.oracle_result;
        result.market_id = market_id;
        result.outcome = outcome;
        result.confidence = confidence;
        result.ipfs_cid = ipfs_cid;
        result.agent_count = agent_count;
        result.source_count = source_count;
        result.agreement_ratio = agreement_ratio;
        result.submitted_at = Clock::get()?.unix_timestamp;
        result.submitter = ctx.accounts.oracle_operator.key();
        
        emit!(OracleResultSubmitted {
            market_id,
            outcome,
            confidence,
            ipfs_cid: result.ipfs_cid.clone(),
            source_count,
        });
        
        Ok(())
    }
}

#[account]
pub struct OracleResult {
    pub market_id: u64,
    pub outcome: u8,
    pub confidence: u16,
    pub ipfs_cid: String,       // Max 64 chars
    pub agent_count: u8,
    pub source_count: u16,
    pub agreement_ratio: u16,
    pub submitted_at: i64,
    pub submitter: Pubkey,
}

#[event]
pub struct OracleResultSubmitted {
    pub market_id: u64,
    pub outcome: u8,
    pub confidence: u16,
    pub ipfs_cid: String,
    pub source_count: u16,
}

#[error_code]
pub enum OracleError {
    #[msg("Insufficient agents (minimum 3)")]
    InsufficientAgents,
    #[msg("Insufficient consensus (minimum 67%)")]
    InsufficientConsensus,
    #[msg("Insufficient sources (minimum 50)")]
    InsufficientSources,
}
```

---

## 6. Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|------------|
| **Gemini API manipulation** | Multiple agents, cross-verify results |
| **Source spoofing** | Validate URLs, check credibility scores |
| **Agent collusion** | Different search strategies, isolated execution |
| **Timing attacks** | Lock research period, atomic reveal |
| **IPFS censorship** | Pin to multiple gateways |

### Future Improvements

1. **Agent Diversity**: Add OpenAI, Anthropic agents when APIs available
2. **Decentralized Agents**: Community-run agent nodes
3. **Economic Security**: Stake-based slashing for incorrect results
4. **Zero-Knowledge Proofs**: Prove research without revealing sources

---

## 7. API Reference

### REST API

```
POST /api/v1/resolve
{
  "market_id": 123,
  "question": "Did X happen?",
  "resolution_criteria": "...",
  "deadline": "2025-12-31T23:59:59Z"
}

Response:
{
  "request_id": "req_abc123",
  "status": "processing",
  "estimated_time_seconds": 120
}
```

```
GET /api/v1/result/{request_id}

Response:
{
  "request_id": "req_abc123",
  "status": "completed",
  "result": {
    "outcome": "YES",
    "confidence": 0.85,
    "agreement_ratio": 1.0,
    "source_count": 155,
    "ipfs_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
    "agents": [...]
  }
}
```

---

*For implementation details, see the source code in `/agents`, `/consensus`, and `/storage` directories.*
