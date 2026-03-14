"""
Multi-Agent Oracle - Core Implementation

The main oracle class that orchestrates multiple agents,
calculates consensus, and stores results.
"""

import asyncio
import os
import uuid
from datetime import datetime

import structlog
from pydantic import BaseModel, Field

from oracle.agents import BaseAgent, GeminiDeepResearchAgent, SearchStrategy
from oracle.consensus import ConsensusConfig, ConsensusEngine
from oracle.consensus.multi_outcome_engine import MultiOutcomeConsensusConfig, MultiOutcomeConsensusEngine
from oracle.models import (
    AgentResult,
    MultiOutcome,
    MultiOutcomeAgentResult,
    MultiOutcomeConsensusResult,
    MultiOutcomeOracleResult,
    OracleRequest,
    OracleResult,
    Outcome,
)
from oracle.storage import IPFSStorage

logger = structlog.get_logger()


class OracleConfig(BaseModel):
    """Configuration for the Multi-Agent Oracle."""

    # Agent settings
    num_agents: int = Field(default=3, ge=1, le=10)
    agent_timeout_seconds: int = Field(default=300)

    # Consensus settings (overridden in __init__ from env CONSENSUS_THRESHOLD)
    consensus_threshold: float = Field(default=0.66, ge=0.5, le=1.0)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Storage settings
    enable_ipfs: bool = Field(default=True)

    # Blockchain settings
    auto_submit: bool = Field(default=False)


class MultiAgentOracle:
    """
    Multi-Agent Deep Research Oracle.

    Orchestrates multiple AI agents to research prediction market
    questions, calculates consensus, and stores results on IPFS.

    Usage:
        oracle = MultiAgentOracle()
        result = await oracle.resolve(
            question="Did X happen?",
            resolution_criteria="...",
        )
    """

    def __init__(
        self,
        agents: list[BaseAgent] | None = None,
        config: OracleConfig | None = None,
        consensus_engine: ConsensusEngine | None = None,
        ipfs_storage: IPFSStorage | None = None,
    ):
        self.config = config or OracleConfig()

        # Initialize agents
        if agents:
            self.agents = agents
        else:
            self.agents = self._create_default_agents()

        # Initialize consensus engine
        import os

        min_valid = int(os.getenv("MIN_VALID_AGENTS", "2"))
        threshold = float(os.getenv("CONSENSUS_THRESHOLD", "0.66"))
        self.consensus_engine = consensus_engine or ConsensusEngine(
            ConsensusConfig(
                threshold=threshold,
                min_agents=min_valid,
            )
        )

        # Initialize IPFS storage
        if self.config.enable_ipfs:
            self.ipfs_storage = ipfs_storage or IPFSStorage()
        else:
            self.ipfs_storage = None

        logger.info(
            "Initialized Multi-Agent Oracle",
            num_agents=len(self.agents),
            consensus_threshold=self.config.consensus_threshold,
            ipfs_enabled=self.config.enable_ipfs,
        )

    def _create_default_agents(self) -> list[BaseAgent]:
        """Create default set of Gemini agents with different strategies and API keys."""

        base_strategies = [
            SearchStrategy.COMPREHENSIVE,
            SearchStrategy.FOCUSED,
            SearchStrategy.DIVERSE,
        ]

        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        num_agents = int(os.getenv("MIN_AGENTS", str(self.config.num_agents)))

        # Collect all available API keys for distribution
        api_keys = [
            k
            for k in [
                os.getenv("GEMINI_API_KEY"),
                os.getenv("GEMINI_API_KEY_2"),
                os.getenv("GEMINI_API_KEY_3"),
            ]
            if k
        ]

        if not api_keys:
            logger.error("No GEMINI_API_KEY configured!")

        agents = []
        for i in range(num_agents):
            strategy = base_strategies[i % len(base_strategies)]
            api_key = api_keys[i % len(api_keys)] if api_keys else None
            key_suffix = f"...{api_key[-4:]}" if api_key else "NONE"
            agent = GeminiDeepResearchAgent(
                api_key=api_key,
                agent_id=f"gemini-agent-{i + 1}",
                strategy=strategy,
                model=model,
            )
            logger.info(f"Agent {i + 1} → key={key_suffix}, strategy={strategy.value}")
            agents.append(agent)

        return agents

    async def resolve(
        self,
        question: str,
        resolution_criteria: str,
        market_id: int | None = None,
        deadline: str | None = None,
        callback_url: str | None = None,
    ) -> OracleResult:
        """
        Resolve a prediction market question.

        Args:
            question: The question to resolve
            resolution_criteria: Criteria for determining the outcome
            market_id: Optional market ID for blockchain submission
            deadline: Optional deadline for the question
            callback_url: Optional webhook URL for async notification

        Returns:
            OracleResult with consensus, sources, and IPFS hash
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        market_id = market_id or 0
        started_at = datetime.utcnow().isoformat()

        logger.info(
            "Starting resolution",
            request_id=request_id,
            question=question[:100],
            num_agents=len(self.agents),
        )

        # Create request
        OracleRequest(
            request_id=request_id,
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            deadline=deadline,
            callback_url=callback_url,
        )

        # Run agents with internal retry loop
        max_retries = int(os.getenv("MAX_AGENT_RETRIES", "10"))
        retry_base_delay = float(os.getenv("AGENT_RETRY_BASE_DELAY", "2"))
        min_valid = self.consensus_engine.config.min_agents

        agent_results = []
        for attempt in range(max_retries):
            agent_results = await self._run_agents(question, resolution_criteria, deadline)
            valid_count = sum(1 for r in agent_results if r.is_valid)

            if valid_count >= min_valid:
                if attempt > 0:
                    logger.info(
                        f"✅ Retry succeeded on attempt {attempt + 1}/{max_retries}: {valid_count} valid agents"
                    )
                break

            if attempt < max_retries - 1:
                delay = min(retry_base_delay * (2**attempt), 30)
                failed_errors = [r.error for r in agent_results if r.error]
                logger.warning(
                    f"⚠️ Attempt {attempt + 1}/{max_retries}: only {valid_count}/{len(agent_results)} valid agents. "
                    f"Retrying in {delay:.0f}s... Errors: {failed_errors[:3]}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"❌ All {max_retries} attempts exhausted. valid_agents={valid_count}/{len(agent_results)}. "
                    f"Proceeding with best available results."
                )

        # Calculate consensus from best attempt
        consensus = self.consensus_engine.calculate(agent_results)

        # Merge sources from agreeing agents
        if consensus.reached:
            agreeing_results = [r for r in agent_results if r.outcome == consensus.outcome]
            merged_sources = self.consensus_engine._merge_sources(agreeing_results)
        else:
            merged_sources = []

        # Store on IPFS
        ipfs_cid = None
        if self.ipfs_storage and (consensus.reached or len(agent_results) > 0):
            try:
                ipfs_cid = await self.ipfs_storage.store_research(
                    market_id=market_id,
                    question=question,
                    resolution_criteria=resolution_criteria,
                    agent_results=agent_results,
                    consensus=consensus,
                    merged_sources=merged_sources,
                )
            except Exception as e:
                logger.error(f"IPFS storage failed: {e}")

        # Build result
        result = OracleResult(
            request_id=request_id,
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            consensus=consensus,
            agent_results=agent_results,
            merged_sources=merged_sources,
            ipfs_cid=ipfs_cid,
            research_started_at=started_at,
            research_completed_at=datetime.utcnow().isoformat(),
        )

        logger.info(
            "Resolution completed",
            request_id=request_id,
            outcome=consensus.outcome.value,
            consensus_reached=consensus.reached,
            confidence=f"{consensus.confidence:.1%}",
            source_count=len(merged_sources),
            ipfs_cid=ipfs_cid,
        )

        return result

    async def resolve_multi_outcome(
        self,
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        market_id: int | None = None,
        deadline: str | None = None,
        consensus_threshold: float | None = None,
    ) -> MultiOutcomeOracleResult:
        """
        Resolve a multi-outcome prediction market question.

        Runs agents with multi-outcome prompts, then uses
        MultiOutcomeConsensusEngine for N+1 bin voting.
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        market_id = market_id or 0
        started_at = datetime.utcnow().isoformat()

        logger.info(
            "Starting multi-outcome resolution",
            request_id=request_id,
            question=question[:100],
            num_outcomes=len(outcomes),
            outcomes=outcomes,
            num_agents=len(self.agents),
        )

        # Run agents with retry loop
        max_retries = int(os.getenv("MAX_AGENT_RETRIES", "10"))
        retry_base_delay = float(os.getenv("AGENT_RETRY_BASE_DELAY", "2"))

        threshold = consensus_threshold or float(os.getenv("MULTI_OUTCOME_CONSENSUS_THRESHOLD", "0.80"))
        mo_engine = MultiOutcomeConsensusEngine(
            MultiOutcomeConsensusConfig(
                threshold=threshold,
                min_agents=self.consensus_engine.config.min_agents,
            )
        )
        min_valid = mo_engine.config.min_agents

        agent_results: list[MultiOutcomeAgentResult] = []
        for attempt in range(max_retries):
            agent_results = await self._run_agents_multi_outcome(question, resolution_criteria, outcomes, deadline)
            valid_count = sum(1 for r in agent_results if r.is_valid)

            if valid_count >= min_valid:
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}/{max_retries}: {valid_count} valid agents")
                break

            if attempt < max_retries - 1:
                delay = min(retry_base_delay * (2 ** attempt), 30)
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: only {valid_count}/{len(agent_results)} valid agents. Retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts exhausted. valid_agents={valid_count}/{len(agent_results)}.")

        # Calculate consensus
        consensus = mo_engine.calculate(agent_results, outcomes)

        # Merge sources from agreeing agents
        if consensus.reached:
            winning_label = consensus.winning_outcome.outcome_label
            agreeing = [r for r in agent_results if r.outcome_label == winning_label]
            merged_sources = mo_engine._merge_sources(agreeing)
        else:
            merged_sources = []

        # Store on IPFS
        ipfs_cid = None
        if self.ipfs_storage and len(agent_results) > 0:
            try:
                # Build a compatible structure for IPFS storage
                binary_results = []
                for r in agent_results:
                    binary_results.append(AgentResult(
                        agent_id=r.agent_id,
                        model=r.model,
                        strategy=r.strategy,
                        outcome=Outcome.YES if r.outcome_index >= 0 else Outcome.UNDETERMINED,
                        confidence=r.confidence,
                        reasoning=f"[Multi-outcome: {r.outcome_label} (index={r.outcome_index})] {r.reasoning}",
                        sources=r.sources,
                    ))
                from oracle.models import ConsensusResult as BinaryConsensusResult
                binary_consensus = BinaryConsensusResult(
                    reached=consensus.reached,
                    outcome=Outcome.YES if consensus.winning_outcome.is_determined else Outcome.UNDETERMINED,
                    confidence=consensus.confidence,
                    agreement_ratio=consensus.agreement_ratio,
                    weighted_ratio=consensus.weighted_ratio,
                    agent_count=consensus.agent_count,
                )
                ipfs_cid = await self.ipfs_storage.store_research(
                    market_id=market_id,
                    question=question,
                    resolution_criteria=resolution_criteria,
                    agent_results=binary_results,
                    consensus=binary_consensus,
                    merged_sources=merged_sources,
                )
            except Exception as e:
                logger.error(f"IPFS storage failed: {e}")

        result = MultiOutcomeOracleResult(
            request_id=request_id,
            market_id=market_id,
            question=question,
            resolution_criteria=resolution_criteria,
            outcomes=outcomes,
            consensus=consensus,
            agent_results=agent_results,
            merged_sources=merged_sources,
            ipfs_cid=ipfs_cid,
            research_started_at=started_at,
            research_completed_at=datetime.utcnow().isoformat(),
        )

        logger.info(
            "Multi-outcome resolution completed",
            request_id=request_id,
            outcome_index=consensus.winning_outcome.outcome_index,
            outcome_label=consensus.winning_outcome.outcome_label,
            consensus_reached=consensus.reached,
            confidence=f"{consensus.confidence:.1%}",
        )

        return result

    async def _run_agents_multi_outcome(
        self,
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        deadline: str | None = None,
    ) -> list[MultiOutcomeAgentResult]:
        """Run all agents in parallel for multi-outcome resolution."""

        async def run_agent(agent: BaseAgent) -> MultiOutcomeAgentResult:
            try:
                if isinstance(agent, GeminiDeepResearchAgent):
                    return await asyncio.wait_for(
                        agent.research_multi_outcome(question, resolution_criteria, outcomes, deadline),
                        timeout=self.config.agent_timeout_seconds,
                    )
                else:
                    # Fallback for non-Gemini agents: use binary research and map
                    binary_result = await asyncio.wait_for(
                        agent.research(question, resolution_criteria, deadline),
                        timeout=self.config.agent_timeout_seconds,
                    )
                    return MultiOutcomeAgentResult(
                        agent_id=binary_result.agent_id,
                        model=binary_result.model,
                        strategy=binary_result.strategy,
                        outcome_index=-1,
                        outcome_label="UNDETERMINED",
                        confidence=binary_result.confidence,
                        reasoning=binary_result.reasoning,
                        sources=binary_result.sources,
                        error=binary_result.error,
                    )
            except TimeoutError:
                logger.warning(f"Agent {agent.agent_id} timed out")
                return MultiOutcomeAgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome_index=-1,
                    outcome_label="UNDETERMINED",
                    confidence=0.0,
                    reasoning="Research timed out",
                    sources=[],
                    error="Timeout",
                )
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} failed: {e}")
                return MultiOutcomeAgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome_index=-1,
                    outcome_label="UNDETERMINED",
                    confidence=0.0,
                    reasoning="Research failed",
                    sources=[],
                    error=str(e),
                )

        tasks = [run_agent(agent) for agent in self.agents]
        results = await asyncio.gather(*tasks)

        successful = [r for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]

        logger.info(
            "Multi-outcome agent research completed",
            total=len(results),
            successful=len(successful),
            failed=len(failed),
        )

        return list(results)

    async def _run_agents(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> list[AgentResult]:
        """Run all agents in parallel and collect results."""

        async def run_agent(agent: BaseAgent) -> AgentResult:
            try:
                return await asyncio.wait_for(
                    agent.research(question, resolution_criteria, deadline),
                    timeout=self.config.agent_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(f"Agent {agent.agent_id} timed out")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research timed out",
                    sources=[],
                    error="Timeout",
                )
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} failed: {e}")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research failed",
                    sources=[],
                    error=str(e),
                )

        # Run all agents in parallel
        tasks = [run_agent(agent) for agent in self.agents]
        results = await asyncio.gather(*tasks)

        # Filter out completely failed results for logging
        successful = [r for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]

        logger.info(
            "Agent research completed",
            total=len(results),
            successful=len(successful),
            failed=len(failed),
        )

        return list(results)

    async def get_result(self, request_id: str) -> OracleResult | None:
        """
        Get result for a previous request.

        Note: In production, this would query a database.
        For now, returns None as results are returned synchronously.
        """
        # TODO: Implement result caching/storage
        return None

    async def close(self):
        """Clean up resources."""
        if self.ipfs_storage:
            await self.ipfs_storage.close()


# Convenience function for simple usage
async def resolve_question(
    question: str,
    resolution_criteria: str,
    num_agents: int = 3,
) -> OracleResult:
    """
    Simple function to resolve a question.

    Usage:
        result = await resolve_question(
            "Did Bitcoin reach $100k?",
            "BTC price >= $100,000 on major exchange",
        )
    """
    oracle = MultiAgentOracle(config=OracleConfig(num_agents=num_agents))

    try:
        return await oracle.resolve(question, resolution_criteria)
    finally:
        await oracle.close()
