"""
Consensus Engine

Calculates consensus from multiple agent results using
weighted voting and source quality analysis.
"""

from typing import Optional
from pydantic import BaseModel, Field
import structlog

from oracle.models import (
    AgentResult,
    ConsensusResult,
    ResearchSource,
    Outcome,
)

logger = structlog.get_logger()


class ConsensusConfig(BaseModel):
    """Configuration for consensus calculation."""
    
    # Minimum agents required
    min_agents: int = Field(default=3, description="Minimum agents required")
    
    # Consensus threshold (0.67 = 2/3 majority)
    threshold: float = Field(default=0.67, ge=0.5, le=1.0)
    
    # Minimum confidence for valid result
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Use weighted voting based on source quality
    use_weighted_voting: bool = Field(default=True)
    
    # Minimum sources per agent
    min_sources_per_agent: int = Field(default=50)


class ConsensusEngine:
    """
    Byzantine Fault Tolerant consensus engine for oracle results.
    
    Requires 2/3+ supermajority for valid consensus.
    Uses weighted voting based on confidence and source quality.
    """
    
    def __init__(self, config: Optional[ConsensusConfig] = None):
        self.config = config or ConsensusConfig()
        logger.info(
            "Initialized consensus engine",
            threshold=self.config.threshold,
            min_agents=self.config.min_agents,
        )
    
    def calculate(self, results: list[AgentResult]) -> ConsensusResult:
        """
        Calculate consensus from agent results.
        
        Args:
            results: List of agent research results
            
        Returns:
            ConsensusResult with outcome and confidence
        """
        logger.info(f"Calculating consensus from {len(results)} agents")
        
        # Validate minimum agents
        if len(results) < self.config.min_agents:
            return ConsensusResult(
                reached=False,
                outcome=Outcome.INVALID,
                reason=f"Need {self.config.min_agents}+ agents, got {len(results)}",
                agent_count=len(results),
                requires_human_review=True,
            )
        
        # Filter valid results
        valid_results = [r for r in results if r.is_valid]
        
        if len(valid_results) < self.config.min_agents:
            return ConsensusResult(
                reached=False,
                outcome=Outcome.INVALID,
                reason=f"Only {len(valid_results)} valid results, need {self.config.min_agents}",
                agent_count=len(results),
                requires_human_review=True,
            )
        
        # Group by outcome
        votes: dict[Outcome, list[AgentResult]] = {
            Outcome.YES: [],
            Outcome.NO: [],
            Outcome.UNDETERMINED: [],
        }
        
        weights: dict[Outcome, float] = {
            Outcome.YES: 0.0,
            Outcome.NO: 0.0,
            Outcome.UNDETERMINED: 0.0,
        }
        
        for result in valid_results:
            outcome = result.outcome
            if outcome in votes:
                votes[outcome].append(result)
                weight = self._calculate_vote_weight(result)
                weights[outcome] += weight
        
        # Calculate ratios
        total_weight = sum(weights.values())
        total_votes = len(valid_results)
        
        # Find winner
        winning_outcome = max(weights.keys(), key=lambda k: weights[k])
        winning_count = len(votes[winning_outcome])
        winning_ratio = winning_count / total_votes if total_votes > 0 else 0
        weighted_ratio = weights[winning_outcome] / total_weight if total_weight > 0 else 0
        
        logger.info(
            "Vote results",
            yes_count=len(votes[Outcome.YES]),
            no_count=len(votes[Outcome.NO]),
            undetermined_count=len(votes[Outcome.UNDETERMINED]),
            winning_outcome=winning_outcome.value,
            winning_ratio=f"{winning_ratio:.1%}",
        )
        
        # Check threshold
        effective_ratio = weighted_ratio if self.config.use_weighted_voting else winning_ratio
        
        if effective_ratio >= self.config.threshold:
            # Consensus reached
            winning_results = votes[winning_outcome]
            merged_sources = self._merge_sources(winning_results)
            avg_confidence = sum(r.confidence for r in winning_results) / len(winning_results)
            
            # Calculate source overlap
            source_overlap = self._calculate_source_overlap(winning_results)
            
            return ConsensusResult(
                reached=True,
                outcome=winning_outcome,
                confidence=avg_confidence,
                agreement_ratio=winning_ratio,
                weighted_ratio=weighted_ratio,
                total_sources=sum(len(r.sources) for r in winning_results),
                unique_sources=len(merged_sources),
                source_overlap=source_overlap,
                agent_count=len(valid_results),
                requires_human_review=False,
            )
        else:
            # No consensus
            return ConsensusResult(
                reached=False,
                outcome=Outcome.UNDETERMINED,
                confidence=0.0,
                agreement_ratio=winning_ratio,
                weighted_ratio=weighted_ratio,
                agent_count=len(valid_results),
                requires_human_review=True,
                reason=f"No supermajority: highest agreement is {winning_ratio:.1%}",
            )
    
    def _calculate_vote_weight(self, result: AgentResult) -> float:
        """Calculate voting weight for an agent's result."""
        # Base: confidence (0-1)
        confidence = result.confidence
        
        # Source quality factor
        source_quality = self._calculate_source_quality(result.sources)
        
        # Source count factor (capped at 1.0)
        source_count_factor = min(len(result.sources) / self.config.min_sources_per_agent, 1.0)
        
        # Final weight
        weight = confidence * source_quality * source_count_factor
        
        return weight
    
    def _calculate_source_quality(self, sources: list[ResearchSource]) -> float:
        """Calculate average source quality score."""
        if not sources:
            return 0.0
        
        # Average credibility
        avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
        
        # Category diversity bonus (0-0.2 based on 5 categories)
        categories = set(s.category for s in sources)
        diversity_bonus = min(len(categories) / 25, 0.2)
        
        return min(avg_credibility + diversity_bonus, 1.0)
    
    def _merge_sources(self, results: list[AgentResult]) -> list[ResearchSource]:
        """Merge and deduplicate sources from agreeing agents."""
        seen_urls: set[str] = set()
        merged: list[ResearchSource] = []
        
        # Collect all sources with their citing agents
        all_sources: list[tuple[ResearchSource, str]] = []
        for result in results:
            for source in result.sources:
                all_sources.append((source, result.agent_id))
        
        # Sort by quality (relevance × credibility)
        all_sources.sort(
            key=lambda x: x[0].relevance_score * x[0].credibility_score,
            reverse=True,
        )
        
        # Deduplicate
        for source, agent_id in all_sources:
            if source.url not in seen_urls:
                # Create new source with cited_by
                new_source = source.model_copy()
                new_source.cited_by = [agent_id]
                merged.append(new_source)
                seen_urls.add(source.url)
            else:
                # Add to existing source's cited_by
                for existing in merged:
                    if existing.url == source.url:
                        if agent_id not in existing.cited_by:
                            existing.cited_by.append(agent_id)
                        break
        
        logger.info(f"Merged {len(merged)} unique sources from {len(results)} agents")
        return merged
    
    def _calculate_source_overlap(self, results: list[AgentResult]) -> float:
        """Calculate average pairwise source overlap between agents."""
        if len(results) < 2:
            return 1.0
        
        overlaps: list[float] = []
        
        # Get URLs for each agent
        agent_urls: list[set[str]] = [
            {s.url for s in r.sources} for r in results
        ]
        
        # Calculate pairwise overlap
        for i in range(len(agent_urls)):
            for j in range(i + 1, len(agent_urls)):
                urls_a = agent_urls[i]
                urls_b = agent_urls[j]
                
                if urls_a and urls_b:
                    intersection = urls_a & urls_b
                    union = urls_a | urls_b
                    overlap = len(intersection) / len(union) if union else 0
                    overlaps.append(overlap)
        
        return sum(overlaps) / len(overlaps) if overlaps else 0.0
    
    def analyze_disagreement(
        self,
        results: list[AgentResult],
    ) -> dict:
        """Analyze why agents disagreed."""
        analysis = {
            "outcomes": {},
            "confidence_range": {},
            "source_differences": [],
            "recommendations": [],
        }
        
        # Group by outcome
        for result in results:
            outcome = result.outcome.value
            if outcome not in analysis["outcomes"]:
                analysis["outcomes"][outcome] = []
            analysis["outcomes"][outcome].append({
                "agent_id": result.agent_id,
                "confidence": result.confidence,
                "source_count": len(result.sources),
            })
        
        # Confidence analysis
        confidences = [r.confidence for r in results]
        analysis["confidence_range"] = {
            "min": min(confidences),
            "max": max(confidences),
            "spread": max(confidences) - min(confidences),
        }
        
        # Recommendations
        if analysis["confidence_range"]["spread"] > 0.3:
            analysis["recommendations"].append(
                "Large confidence spread suggests uncertainty - consider human review"
            )
        
        if len(analysis["outcomes"]) > 2:
            analysis["recommendations"].append(
                "Three-way split - event may need clearer resolution criteria"
            )
        
        return analysis
