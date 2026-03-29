"""
Multi-Agent Oracle - Core Implementation

The main oracle class that orchestrates multiple agents,
calculates consensus, and stores results.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

from oracle.agents import BaseAgent, GeminiDeepResearchAgent, SearchStrategy
from oracle.agents.base import ProgressCallback
from oracle.consensus import ConsensusConfig, ConsensusEngine
from oracle.consensus.multi_outcome_engine import (
    MultiOutcomeConsensusConfig,
    MultiOutcomeConsensusEngine,
)
from oracle.models import (
    AgentResult,
    MultiOutcomeAgentResult,
    MultiOutcomeOracleResult,
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

        use_vertex = os.getenv("USE_VERTEX_AI", "false").lower() == "true"

        if not use_vertex:
            raise RuntimeError(
                "Vertex AI is required. "
                "Set USE_VERTEX_AI=true and provide GOOGLE_APPLICATION_CREDENTIALS_JSON."
            )

        agents = []
        for i in range(num_agents):
            strategy = base_strategies[i % len(base_strategies)]
            agent = GeminiDeepResearchAgent(
                agent_id=f"gemini-agent-{i + 1}",
                strategy=strategy,
                model=model,
            )
            logger.info(f"Agent {i + 1} → Vertex AI, strategy={strategy.value}")
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
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Starting resolution",
            request_id=request_id,
            question=question[:100],
            num_agents=len(self.agents),
        )

        max_retries = int(os.getenv("MAX_AGENT_RETRIES", "10"))
        retry_base_delay = float(os.getenv("AGENT_RETRY_BASE_DELAY", "2"))
        min_valid = self.consensus_engine.config.min_agents

        agent_results = await self._run_agents(question, resolution_criteria, deadline)

        for attempt in range(1, max_retries):
            valid_count = sum(1 for r in agent_results if r.is_valid)
            if valid_count >= min_valid:
                if attempt > 1:
                    logger.info(
                        f"✅ Retry succeeded on attempt {attempt}/{max_retries}: {valid_count} valid agents"
                    )
                break

            failed_indices = [i for i, r in enumerate(agent_results) if not r.is_valid]
            failed_agents = [self.agents[i] for i in failed_indices]
            failed_errors = [agent_results[i].error for i in failed_indices]

            delay = min(retry_base_delay * (2 ** (attempt - 1)), 30)
            logger.warning(
                f"⚠️ Attempt {attempt}/{max_retries}: only {valid_count}/{len(agent_results)} valid agents. "
                f"Retrying {len(failed_agents)} failed agents in {delay:.0f}s... Errors: {failed_errors[:3]}"
            )
            await asyncio.sleep(delay)

            retry_results = await self._run_agents_subset(
                failed_agents, question, resolution_criteria, deadline
            )
            for idx, retry_result in zip(failed_indices, retry_results):
                agent_results[idx] = retry_result
        else:
            valid_count = sum(1 for r in agent_results if r.is_valid)
            if valid_count < min_valid:
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
            research_completed_at=datetime.now(timezone.utc).isoformat(),
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
        started_at = datetime.now(timezone.utc).isoformat()

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

        agent_results = await self._run_agents_multi_outcome(question, resolution_criteria, outcomes, deadline)

        for attempt in range(1, max_retries):
            valid_count = sum(1 for r in agent_results if r.is_valid)
            if valid_count >= min_valid:
                if attempt > 1:
                    logger.info(
                        f"✅ Multi-outcome retry succeeded on attempt {attempt}/{max_retries}: {valid_count} valid agents"
                    )
                break

            failed_indices = [i for i, r in enumerate(agent_results) if not r.is_valid]
            failed_agents = [self.agents[i] for i in failed_indices]
            failed_errors = [agent_results[i].error for i in failed_indices]

            delay = min(retry_base_delay * (2 ** (attempt - 1)), 30)
            logger.warning(
                f"⚠️ Multi-outcome attempt {attempt}/{max_retries}: only {valid_count}/{len(agent_results)} valid. "
                f"Retrying {len(failed_agents)} failed agents in {delay:.0f}s... Errors: {failed_errors[:3]}"
            )
            await asyncio.sleep(delay)

            retry_results = await self._run_agents_multi_outcome_subset(
                failed_agents, question, resolution_criteria, outcomes, deadline
            )
            for idx, retry_result in zip(failed_indices, retry_results):
                agent_results[idx] = retry_result
        else:
            valid_count = sum(1 for r in agent_results if r.is_valid)
            if valid_count < min_valid:
                logger.error(
                    f"❌ All {max_retries} multi-outcome attempts exhausted. valid_agents={valid_count}/{len(agent_results)}. "
                    f"Proceeding with best available results."
                )

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
            research_completed_at=datetime.now(timezone.utc).isoformat(),
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

    async def _run_agents_multi_outcome_subset(
        self,
        agents: list[BaseAgent],
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        deadline: str | None = None,
    ) -> list[MultiOutcomeAgentResult]:
        """Re-run a subset of agents for multi-outcome resolution (retry only failed)."""

        async def run_agent(agent: BaseAgent) -> MultiOutcomeAgentResult:
            try:
                if isinstance(agent, GeminiDeepResearchAgent):
                    return await asyncio.wait_for(
                        agent.research_multi_outcome(question, resolution_criteria, outcomes, deadline),
                        timeout=self.config.agent_timeout_seconds,
                    )
                else:
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
                logger.warning(f"Agent {agent.agent_id} timed out (multi-outcome retry)")
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
                logger.error(f"Agent {agent.agent_id} failed (multi-outcome retry): {e}")
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

        tasks = [run_agent(agent) for agent in agents]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _run_agents_subset_with_progress(
        self,
        agents: list[BaseAgent],
        question: str,
        resolution_criteria: str,
        deadline: str | None,
        callback_factory,
        original_indices: list[int],
    ) -> list[AgentResult]:
        """Re-run failed agents with progress callbacks."""

        async def run_agent(agent: BaseAgent, original_index: int) -> AgentResult:
            cb = await callback_factory(original_index)
            try:
                return await asyncio.wait_for(
                    agent.research(question, resolution_criteria, deadline, progress_callback=cb),
                    timeout=self.config.agent_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(f"Agent {agent.agent_id} timed out (retry)")
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
                logger.error(f"Agent {agent.agent_id} failed (retry): {e}")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research failed",
                    sources=[],
                    error=str(e),
                )

        tasks = [run_agent(agent, idx) for agent, idx in zip(agents, original_indices)]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _run_agents_multi_outcome_subset_with_progress(
        self,
        agents: list[BaseAgent],
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        deadline: str | None,
        callback_factory,
        original_indices: list[int],
    ) -> list[MultiOutcomeAgentResult]:
        """Re-run failed multi-outcome agents with progress callbacks."""

        async def run_agent(agent: BaseAgent, original_index: int) -> MultiOutcomeAgentResult:
            cb = await callback_factory(original_index)
            try:
                if isinstance(agent, GeminiDeepResearchAgent):
                    return await asyncio.wait_for(
                        agent.research_multi_outcome(question, resolution_criteria, outcomes, deadline, progress_callback=cb),
                        timeout=self.config.agent_timeout_seconds,
                    )
                else:
                    binary_result = await asyncio.wait_for(
                        agent.research(question, resolution_criteria, deadline, progress_callback=cb),
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
                logger.warning(f"Agent {agent.agent_id} timed out (multi-outcome retry)")
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
                logger.error(f"Agent {agent.agent_id} failed (multi-outcome retry): {e}")
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

        tasks = [run_agent(agent, idx) for agent, idx in zip(agents, original_indices)]
        results = await asyncio.gather(*tasks)
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

    async def _run_agents_subset(
        self,
        agents: list[BaseAgent],
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> list[AgentResult]:
        """Re-run a subset of agents (for retrying only failed agents)."""

        async def run_agent(agent: BaseAgent) -> AgentResult:
            try:
                return await asyncio.wait_for(
                    agent.research(question, resolution_criteria, deadline),
                    timeout=self.config.agent_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(f"Agent {agent.agent_id} timed out (retry)")
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
                logger.error(f"Agent {agent.agent_id} failed (retry): {e}")
                return AgentResult(
                    agent_id=agent.agent_id,
                    model=agent.model_name,
                    outcome=Outcome.INVALID,
                    confidence=0.0,
                    reasoning="Research failed",
                    sources=[],
                    error=str(e),
                )

        tasks = [run_agent(agent) for agent in agents]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def resolve_with_progress(
        self,
        question: str,
        resolution_criteria: str,
        market_id: int | None = None,
        deadline: str | None = None,
        request_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Resolve a binary prediction market question with SSE progress events.

        Yields dict events suitable for SSE serialization. Final event has
        event_type="resolution:completed" or "resolution:error".
        """
        request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        market_id = market_id or 0
        started_at = datetime.now(timezone.utc).isoformat()

        yield {
            "event_type": "resolution:started",
            "requestId": request_id,
            "marketId": market_id,
            "agentCount": len(self.agents),
            "marketType": "binary",
        }

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        completed_agents: set[int] = set()

        async def _agent_callback(agent_index: int):
            """Create a per-agent callback that wraps events with agent index."""

            async def _cb(event: dict[str, Any]):
                enriched = {**event, "agentIndex": agent_index}
                try:
                    queue.put_nowait(enriched)
                except asyncio.QueueFull:
                    logger.warning("SSE event queue full, dropping event: %s", event.get("event_type"))
                if event.get("event_type") == "agent_completed":
                    completed_agents.add(agent_index)
                    try:
                        queue.put_nowait({
                            "event_type": "resolution:progress",
                            "agentsCompleted": len(completed_agents),
                            "agentsTotal": len(self.agents),
                        })
                    except asyncio.QueueFull:
                        pass

            return _cb

        max_retries = int(os.getenv("MAX_AGENT_RETRIES", "10"))
        retry_base_delay = float(os.getenv("AGENT_RETRY_BASE_DELAY", "2"))
        min_valid = self.consensus_engine.config.min_agents

        try:
            agents_task = asyncio.create_task(
                self._run_agents_with_progress(
                    question, resolution_criteria, deadline, _agent_callback
                )
            )

            try:
                while not agents_task.done():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield event
                    except asyncio.TimeoutError:
                        continue

                agent_results = agents_task.result()
            except GeneratorExit:
                agents_task.cancel()
                try:
                    await agents_task
                except (asyncio.CancelledError, Exception):
                    pass
                return

            while not queue.empty():
                yield queue.get_nowait()

            for attempt in range(1, max_retries):
                valid_count = sum(1 for r in agent_results if r.is_valid)
                if valid_count >= min_valid:
                    break

                failed_indices = [i for i, r in enumerate(agent_results) if not r.is_valid]
                failed_agents = [self.agents[i] for i in failed_indices]
                delay = min(retry_base_delay * (2 ** (attempt - 1)), 30)

                yield {
                    "event_type": "resolution:retrying",
                    "attempt": attempt,
                    "maxRetries": max_retries,
                    "failedAgentCount": len(failed_agents),
                    "agentsRetrying": [a.agent_id for a in failed_agents],
                }

                await asyncio.sleep(delay)
                retry_results = await self._run_agents_subset_with_progress(
                    failed_agents, question, resolution_criteria, deadline, _agent_callback, failed_indices
                )
                for idx, retry_result in zip(failed_indices, retry_results):
                    agent_results[idx] = retry_result

                while not queue.empty():
                    yield queue.get_nowait()

            consensus = self.consensus_engine.calculate(agent_results)

            if consensus.reached:
                agreeing_results = [r for r in agent_results if r.outcome == consensus.outcome]
                merged_sources = self.consensus_engine._merge_sources(agreeing_results)
            else:
                merged_sources = []

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
                research_completed_at=datetime.now(timezone.utc).isoformat(),
            )

            valid_count = sum(1 for r in agent_results if r.is_valid)
            completed_at = datetime.now(timezone.utc).isoformat()

            yield {
                "event_type": "resolution:completed",
                "requestId": request_id,
                "outcome": consensus.outcome.value,
                "confidence": consensus.confidence,
                "consensusReached": consensus.reached,
                "agreementRatio": consensus.agreement_ratio,
                "weightedRatio": consensus.weighted_ratio,
                "sourceCount": len(merged_sources),
                "ipfsCid": ipfs_cid,
                "agentCount": len(agent_results),
                "validAgentCount": valid_count,
                "requiresManualReview": not consensus.reached,
                "researchStartedAt": started_at,
                "researchCompletedAt": completed_at,
                "_result": result,
            }

        except Exception as e:
            logger.error(f"Resolution with progress failed: {e}")
            yield {
                "event_type": "resolution:error",
                "requestId": request_id,
                "error": str(e),
            }

    async def resolve_multi_outcome_with_progress(
        self,
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        market_id: int | None = None,
        deadline: str | None = None,
        consensus_threshold: float | None = None,
        request_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Resolve a multi-outcome prediction market question with SSE progress events.
        """
        request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        market_id = market_id or 0
        started_at = datetime.now(timezone.utc).isoformat()

        yield {
            "event_type": "resolution:started",
            "requestId": request_id,
            "marketId": market_id,
            "agentCount": len(self.agents),
            "marketType": "multi_outcome",
            "outcomeCount": len(outcomes),
        }

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        completed_agents: set[int] = set()

        async def _agent_callback(agent_index: int):

            async def _cb(event: dict[str, Any]):
                enriched = {**event, "agentIndex": agent_index}
                try:
                    queue.put_nowait(enriched)
                except asyncio.QueueFull:
                    logger.warning("SSE event queue full, dropping event: %s", event.get("event_type"))
                if event.get("event_type") == "agent_completed":
                    completed_agents.add(agent_index)
                    try:
                        queue.put_nowait({
                            "event_type": "resolution:progress",
                            "agentsCompleted": len(completed_agents),
                            "agentsTotal": len(self.agents),
                        })
                    except asyncio.QueueFull:
                        pass

            return _cb

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

        try:
            agents_task = asyncio.create_task(
                self._run_agents_multi_outcome_with_progress(
                    question, resolution_criteria, outcomes, deadline, _agent_callback
                )
            )

            try:
                while not agents_task.done():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield event
                    except asyncio.TimeoutError:
                        continue

                agent_results = agents_task.result()
            except GeneratorExit:
                agents_task.cancel()
                try:
                    await agents_task
                except (asyncio.CancelledError, Exception):
                    pass
                return

            while not queue.empty():
                yield queue.get_nowait()

            for attempt in range(1, max_retries):
                valid_count = sum(1 for r in agent_results if r.is_valid)
                if valid_count >= min_valid:
                    break

                failed_indices = [i for i, r in enumerate(agent_results) if not r.is_valid]
                failed_agents = [self.agents[i] for i in failed_indices]
                delay = min(retry_base_delay * (2 ** (attempt - 1)), 30)

                yield {
                    "event_type": "resolution:retrying",
                    "attempt": attempt,
                    "maxRetries": max_retries,
                    "failedAgentCount": len(failed_agents),
                    "agentsRetrying": [a.agent_id for a in failed_agents],
                }

                await asyncio.sleep(delay)
                retry_results = await self._run_agents_multi_outcome_subset_with_progress(
                    failed_agents, question, resolution_criteria, outcomes, deadline, _agent_callback, failed_indices
                )
                for idx, retry_result in zip(failed_indices, retry_results):
                    agent_results[idx] = retry_result

                while not queue.empty():
                    yield queue.get_nowait()

            consensus = mo_engine.calculate(agent_results, outcomes)

            if consensus.reached:
                winning_label = consensus.winning_outcome.outcome_label
                agreeing = [r for r in agent_results if r.outcome_label == winning_label]
                merged_sources = mo_engine._merge_sources(agreeing)
            else:
                merged_sources = []

            ipfs_cid = None
            if self.ipfs_storage and len(agent_results) > 0:
                try:
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
                research_completed_at=datetime.now(timezone.utc).isoformat(),
            )

            winning = consensus.winning_outcome
            valid_count = sum(1 for r in agent_results if r.is_valid)
            completed_at = datetime.now(timezone.utc).isoformat()

            yield {
                "event_type": "resolution:completed",
                "requestId": request_id,
                "outcomeIndex": winning.outcome_index if winning.is_determined else -1,
                "outcomeLabel": winning.outcome_label,
                "confidence": consensus.confidence,
                "consensusReached": consensus.reached,
                "agreementRatio": consensus.agreement_ratio,
                "weightedRatio": consensus.weighted_ratio,
                "sourceCount": len(merged_sources),
                "ipfsCid": ipfs_cid,
                "agentCount": len(agent_results),
                "validAgentCount": valid_count,
                "requiresManualReview": not consensus.reached or consensus.requires_human_review,
                "researchStartedAt": started_at,
                "researchCompletedAt": completed_at,
                "_result": result,
            }

        except Exception as e:
            logger.error(f"Multi-outcome resolution with progress failed: {e}")
            yield {
                "event_type": "resolution:error",
                "requestId": request_id,
                "error": str(e),
            }

    async def _run_agents_with_progress(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None,
        callback_factory,
    ) -> list[AgentResult]:
        """Run all agents in parallel with progress callbacks."""

        async def run_agent(agent: BaseAgent, index: int) -> AgentResult:
            cb = await callback_factory(index)
            try:
                return await asyncio.wait_for(
                    agent.research(question, resolution_criteria, deadline, progress_callback=cb),
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

        tasks = [run_agent(agent, i) for i, agent in enumerate(self.agents)]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _run_agents_multi_outcome_with_progress(
        self,
        question: str,
        resolution_criteria: str,
        outcomes: list[str],
        deadline: str | None,
        callback_factory,
    ) -> list[MultiOutcomeAgentResult]:
        """Run all agents in parallel for multi-outcome with progress callbacks."""

        async def run_agent(agent: BaseAgent, index: int) -> MultiOutcomeAgentResult:
            cb = await callback_factory(index)
            try:
                if isinstance(agent, GeminiDeepResearchAgent):
                    return await asyncio.wait_for(
                        agent.research_multi_outcome(
                            question, resolution_criteria, outcomes, deadline, progress_callback=cb
                        ),
                        timeout=self.config.agent_timeout_seconds,
                    )
                else:
                    binary_result = await asyncio.wait_for(
                        agent.research(question, resolution_criteria, deadline, progress_callback=cb),
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

        tasks = [run_agent(agent, i) for i, agent in enumerate(self.agents)]
        results = await asyncio.gather(*tasks)
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
