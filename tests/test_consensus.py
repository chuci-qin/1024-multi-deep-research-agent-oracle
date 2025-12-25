"""
Tests for the Consensus Engine.
"""

import pytest

from oracle.consensus import ConsensusConfig, ConsensusEngine
from oracle.models import AgentResult, Outcome


class TestConsensusEngine:
    """Tests for ConsensusEngine."""

    def test_consensus_with_full_agreement(self, sample_agent_results):
        """Test consensus when all agents agree."""
        engine = ConsensusEngine(ConsensusConfig(threshold=0.67, min_agents=3))

        result = engine.calculate(sample_agent_results)

        assert result.reached is True
        assert result.outcome == Outcome.YES
        assert result.agreement_ratio == 1.0
        assert result.agent_count == 3

    def test_consensus_with_supermajority(self, sample_sources):
        """Test consensus with 2/3 majority."""
        results = [
            AgentResult(
                agent_id="agent-1",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.85,
                reasoning="YES",
                sources=sample_sources[:50],
            ),
            AgentResult(
                agent_id="agent-2",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.82,
                reasoning="YES",
                sources=sample_sources[:50],
            ),
            AgentResult(
                agent_id="agent-3",
                model="gemini",
                outcome=Outcome.NO,
                confidence=0.65,
                reasoning="NO",
                sources=sample_sources[:50],
            ),
        ]

        engine = ConsensusEngine(ConsensusConfig(threshold=0.67, min_agents=3))
        result = engine.calculate(results)

        assert result.reached is True
        assert result.outcome == Outcome.YES
        assert result.agreement_ratio == pytest.approx(0.67, rel=0.1)

    def test_no_consensus_with_split_vote(self, sample_sources):
        """Test no consensus when votes are split."""
        results = [
            AgentResult(
                agent_id="agent-1",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.55,
                reasoning="YES",
                sources=sample_sources[:50],
            ),
            AgentResult(
                agent_id="agent-2",
                model="gemini",
                outcome=Outcome.NO,
                confidence=0.60,
                reasoning="NO",
                sources=sample_sources[:50],
            ),
            AgentResult(
                agent_id="agent-3",
                model="gemini",
                outcome=Outcome.UNDETERMINED,
                confidence=0.40,
                reasoning="UNDETERMINED",
                sources=sample_sources[:50],
            ),
        ]

        engine = ConsensusEngine(ConsensusConfig(threshold=0.67, min_agents=3))
        result = engine.calculate(results)

        assert result.reached is False
        assert result.outcome == Outcome.UNDETERMINED
        assert result.requires_human_review is True

    def test_insufficient_agents(self, sample_agent_results):
        """Test failure with insufficient agents."""
        engine = ConsensusEngine(ConsensusConfig(min_agents=5))

        result = engine.calculate(sample_agent_results[:2])

        assert result.reached is False
        assert result.outcome == Outcome.INVALID
        assert "Need 5+ agents" in result.reason

    def test_source_merging(self, sample_sources):
        """Test that sources are properly merged and deduplicated."""
        # Create results with overlapping sources
        results = [
            AgentResult(
                agent_id="agent-1",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.85,
                reasoning="YES",
                sources=sample_sources[:30],
            ),
            AgentResult(
                agent_id="agent-2",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.82,
                reasoning="YES",
                sources=sample_sources[10:40],  # Overlapping
            ),
            AgentResult(
                agent_id="agent-3",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.88,
                reasoning="YES",
                sources=sample_sources[20:50],  # Overlapping
            ),
        ]

        engine = ConsensusEngine()
        merged = engine._merge_sources(results)

        # Should have deduplicated sources
        assert len(merged) == 50  # All unique sources from 0-50

        # Some sources should be cited by multiple agents
        multi_cited = [s for s in merged if len(s.cited_by) > 1]
        assert len(multi_cited) > 0

    def test_source_overlap_calculation(self, sample_sources):
        """Test source overlap calculation."""
        # Create results with known overlap
        results = [
            AgentResult(
                agent_id="agent-1",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.85,
                reasoning="YES",
                sources=sample_sources[:30],
            ),
            AgentResult(
                agent_id="agent-2",
                model="gemini",
                outcome=Outcome.YES,
                confidence=0.82,
                reasoning="YES",
                sources=sample_sources[:30],  # Same sources
            ),
        ]

        engine = ConsensusEngine()
        overlap = engine._calculate_source_overlap(results)

        # Should be 100% overlap
        assert overlap == 1.0
