# 🗳️ Consensus Algorithm

> How multiple agents reach agreement on prediction market outcomes

## Overview

The consensus algorithm ensures that oracle results are reliable by requiring multiple independent agents to agree before submitting a result to the blockchain.

## Design Principles

### 1. Byzantine Fault Tolerance

Our consensus is designed to tolerate up to 1/3 faulty or malicious agents:

```
Total Agents: N
Faulty Tolerance: f = (N-1) / 3
Required Agreement: 2/3 + 1

Example with 3 agents:
- Can tolerate: 0 faulty agents
- Required agreement: 2 out of 3 (67%)

Example with 5 agents:
- Can tolerate: 1 faulty agent
- Required agreement: 4 out of 5 (80%)
```

### 2. Weighted Voting

Not all votes are equal. Votes are weighted by:

```
Vote Weight = confidence × source_quality × source_count_factor

Where:
- confidence: Agent's self-reported confidence (0-1)
- source_quality: Average credibility of sources (0-1)
- source_count_factor: min(sources / 50, 1.0)
```

### 3. Source Verification

Consensus requires minimum source thresholds:

| Requirement | Value |
|-------------|-------|
| Min total sources per agent | 50 |
| Min source categories | 5 |
| Min official sources | 5 |
| Min news sources | 15 |

## Algorithm Steps

### Step 1: Collect Agent Results

```python
async def collect_results(
    agents: list[Agent],
    question: str,
    criteria: str,
) -> list[AgentResult]:
    """Run all agents in parallel and collect results."""
    
    # Run agents in parallel (isolated)
    results = await asyncio.gather(
        *[agent.research(question, criteria) for agent in agents],
        return_exceptions=True,
    )
    
    # Filter out failures
    valid_results = [r for r in results if not isinstance(r, Exception)]
    
    return valid_results
```

### Step 2: Validate Results

```python
def validate_results(results: list[AgentResult]) -> ValidationResult:
    """Ensure all results meet minimum requirements."""
    
    issues = []
    
    for result in results:
        # Check source count
        if len(result.sources) < 50:
            issues.append(f"{result.agent_id}: Only {len(result.sources)} sources")
        
        # Check category diversity
        categories = set(s.category for s in result.sources)
        if len(categories) < 5:
            issues.append(f"{result.agent_id}: Only {len(categories)} categories")
        
        # Check outcome is valid
        if result.outcome not in ["YES", "NO", "UNDETERMINED"]:
            issues.append(f"{result.agent_id}: Invalid outcome '{result.outcome}'")
    
    return ValidationResult(
        is_valid=len(issues) == 0,
        issues=issues,
    )
```

### Step 3: Calculate Vote Weights

```python
def calculate_vote_weight(result: AgentResult) -> float:
    """Calculate voting weight for an agent's result."""
    
    # Base confidence (0-1)
    confidence = result.confidence
    
    # Source quality score
    source_quality = calculate_source_quality(result.sources)
    
    # Source count factor (capped at 1.0)
    source_factor = min(len(result.sources) / 50, 1.0)
    
    # Final weight
    weight = confidence * source_quality * source_factor
    
    return weight

def calculate_source_quality(sources: list[ResearchSource]) -> float:
    """Calculate average source quality score."""
    
    if not sources:
        return 0
    
    # Average credibility
    avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
    
    # Category diversity bonus (0-0.2)
    categories = set(s.category for s in sources)
    diversity_bonus = min(len(categories) / 25, 0.2)  # 5 categories = 0.2 bonus
    
    return min(avg_credibility + diversity_bonus, 1.0)
```

### Step 4: Determine Consensus

```python
def determine_consensus(
    results: list[AgentResult],
    threshold: float = 0.67,
) -> ConsensusResult:
    """Determine if agents have reached consensus."""
    
    # Group votes by outcome
    votes = {"YES": [], "NO": [], "UNDETERMINED": []}
    weights = {"YES": 0, "NO": 0, "UNDETERMINED": 0}
    
    for result in results:
        outcome = result.outcome
        weight = calculate_vote_weight(result)
        
        votes[outcome].append(result)
        weights[outcome] += weight
    
    # Find winning outcome
    total_weight = sum(weights.values())
    
    winning_outcome = max(weights.keys(), key=lambda k: weights[k])
    winning_weight = weights[winning_outcome]
    winning_ratio = len(votes[winning_outcome]) / len(results)
    weighted_ratio = winning_weight / total_weight if total_weight > 0 else 0
    
    # Check if consensus reached
    if winning_ratio >= threshold:
        # Consensus reached
        winning_results = votes[winning_outcome]
        merged_sources = merge_sources(winning_results)
        avg_confidence = sum(r.confidence for r in winning_results) / len(winning_results)
        
        return ConsensusResult(
            reached=True,
            outcome=winning_outcome,
            confidence=avg_confidence,
            agreement_ratio=winning_ratio,
            weighted_ratio=weighted_ratio,
            sources=merged_sources,
            agent_results=results,
        )
    else:
        # No consensus
        return ConsensusResult(
            reached=False,
            outcome="UNDETERMINED",
            confidence=0,
            agreement_ratio=winning_ratio,
            weighted_ratio=weighted_ratio,
            sources=[],
            agent_results=results,
            requires_human_review=True,
        )
```

### Step 5: Merge Sources

```python
def merge_sources(results: list[AgentResult]) -> list[ResearchSource]:
    """Merge and deduplicate sources from agreeing agents."""
    
    seen_urls = set()
    merged = []
    
    # Collect all sources
    all_sources = []
    for result in results:
        for source in result.sources:
            all_sources.append((source, result.agent_id))
    
    # Sort by relevance and credibility
    all_sources.sort(
        key=lambda x: x[0].relevance_score * x[0].credibility_score,
        reverse=True,
    )
    
    # Deduplicate
    for source, agent_id in all_sources:
        if source.url not in seen_urls:
            source.cited_by = [agent_id]
            merged.append(source)
            seen_urls.add(source.url)
        else:
            # Add to cited_by list
            existing = next(s for s in merged if s.url == source.url)
            if agent_id not in existing.cited_by:
                existing.cited_by.append(agent_id)
    
    return merged
```

## Consensus Scenarios

### Scenario 1: Full Agreement ✅

```
Agent A: YES (confidence: 0.85, sources: 52)
Agent B: YES (confidence: 0.82, sources: 48)
Agent C: YES (confidence: 0.88, sources: 55)

Agreement Ratio: 100% (3/3)
Weighted Ratio: 100%

Result: ✅ CONSENSUS REACHED
Outcome: YES
Confidence: 85%
Total Sources: 155 (deduplicated)
```

### Scenario 2: Supermajority ✅

```
Agent A: YES (confidence: 0.85, sources: 52)
Agent B: YES (confidence: 0.82, sources: 48)
Agent C: NO  (confidence: 0.65, sources: 51)

Agreement Ratio: 67% (2/3)
Weighted Ratio: 71% (YES has higher confidence)

Result: ✅ CONSENSUS REACHED
Outcome: YES
Confidence: 83.5%
Total Sources: 100 (from agreeing agents)
```

### Scenario 3: No Consensus ❌

```
Agent A: YES (confidence: 0.55, sources: 50)
Agent B: NO  (confidence: 0.60, sources: 52)
Agent C: UNDETERMINED (confidence: 0.40, sources: 48)

Agreement Ratio: 33% (max)

Result: ❌ NO CONSENSUS
Outcome: UNDETERMINED
Requires: Human Review
```

### Scenario 4: Tie with Weighted Resolution ✅

```
Agent A: YES (confidence: 0.90, sources: 60)  # High quality
Agent B: NO  (confidence: 0.50, sources: 45)  # Lower quality
Agent C: YES (confidence: 0.85, sources: 55)  # High quality

Simple Ratio: 67% YES
Weighted Ratio: 78% YES (because YES voters have higher confidence)

Result: ✅ CONSENSUS REACHED
Outcome: YES
```

## Source Overlap Analysis

We track source overlap between agents:

```python
def analyze_source_overlap(results: list[AgentResult]) -> OverlapAnalysis:
    """Analyze how much sources overlap between agents."""
    
    agent_urls = {}
    for result in results:
        agent_urls[result.agent_id] = set(s.url for s in result.sources)
    
    # Calculate pairwise overlap
    overlaps = {}
    agent_ids = list(agent_urls.keys())
    
    for i, agent_a in enumerate(agent_ids):
        for agent_b in agent_ids[i+1:]:
            urls_a = agent_urls[agent_a]
            urls_b = agent_urls[agent_b]
            
            intersection = urls_a & urls_b
            union = urls_a | urls_b
            
            overlap_ratio = len(intersection) / len(union) if union else 0
            overlaps[f"{agent_a}_{agent_b}"] = overlap_ratio
    
    # Average overlap
    avg_overlap = sum(overlaps.values()) / len(overlaps) if overlaps else 0
    
    return OverlapAnalysis(
        pairwise_overlaps=overlaps,
        average_overlap=avg_overlap,
        total_unique_sources=len(set.union(*agent_urls.values())),
    )
```

### Interpretation

| Overlap | Interpretation |
|---------|----------------|
| 0-20% | Low overlap - agents found very different sources |
| 20-40% | Moderate overlap - good diversity with some common sources |
| 40-60% | High overlap - agents found many same sources |
| 60%+ | Very high overlap - possibly limited source availability |

## Edge Cases

### 1. Agent Failure

```python
if len(valid_results) < min_agents:
    return ConsensusResult(
        reached=False,
        outcome="INVALID",
        reason=f"Only {len(valid_results)} agents succeeded, need {min_agents}",
    )
```

### 2. All UNDETERMINED

```python
if all(r.outcome == "UNDETERMINED" for r in results):
    return ConsensusResult(
        reached=True,  # This IS consensus
        outcome="UNDETERMINED",
        confidence=sum(r.confidence for r in results) / len(results),
        reason="All agents determined event is undetermined",
    )
```

### 3. Insufficient Sources

```python
for result in results:
    if len(result.sources) < 50:
        # Exclude from consensus
        results.remove(result)
        logging.warning(f"Excluding {result.agent_id}: insufficient sources")
```

## Confidence Score Calculation

Final confidence is weighted average:

```python
def calculate_final_confidence(
    results: list[AgentResult],
    winning_outcome: str,
) -> float:
    """Calculate final confidence score for consensus."""
    
    agreeing = [r for r in results if r.outcome == winning_outcome]
    
    if not agreeing:
        return 0
    
    # Weighted average by source quality
    total_weight = 0
    weighted_confidence = 0
    
    for result in agreeing:
        weight = calculate_source_quality(result.sources) * len(result.sources)
        weighted_confidence += result.confidence * weight
        total_weight += weight
    
    return weighted_confidence / total_weight if total_weight > 0 else 0
```

## Configuration Options

```yaml
consensus:
  # Minimum agents required
  min_agents: 3
  
  # Agreement threshold (0.67 = 2/3)
  threshold: 0.67
  
  # Use weighted voting
  use_weighted_voting: true
  
  # Minimum confidence for valid result
  min_confidence: 0.5
  
  # Maximum acceptable source overlap
  max_source_overlap: 0.8
  
  # Timeout for agent research (seconds)
  agent_timeout: 300
```

## Metrics and Monitoring

Track these metrics for consensus quality:

```python
@dataclass
class ConsensusMetrics:
    # Agreement metrics
    agreement_ratio: float      # % of agents agreeing
    weighted_agreement: float   # Weighted agreement score
    
    # Source metrics
    total_unique_sources: int   # Deduplicated source count
    avg_sources_per_agent: float
    source_overlap: float       # Average pairwise overlap
    
    # Confidence metrics
    avg_confidence: float
    confidence_std: float       # Std deviation of confidences
    
    # Time metrics
    total_research_time: float  # Seconds
    avg_agent_time: float
```

---

*For implementation details, see `/consensus/engine.py`*
