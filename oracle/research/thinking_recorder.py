"""
Thinking Process Recorder

Records the step-by-step thinking process of an AI agent during research.
This provides transparency and verifiability for the oracle's decision-making.

Task ID: 2.2.1 - 2.2.7 from IMPLEMENTATION-TRACKER.md
"""

from datetime import datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ThinkingStepType(str, Enum):
    """Types of thinking steps during research."""

    # Research initiation
    RESEARCH_START = "research_start"
    QUERY_FORMULATION = "query_formulation"

    # Information gathering
    SEARCH_INITIATED = "search_initiated"
    SOURCE_FOUND = "source_found"
    SOURCE_EVALUATED = "source_evaluated"

    # Analysis
    FACT_EXTRACTED = "fact_extracted"
    CONTRADICTION_DETECTED = "contradiction_detected"
    EVIDENCE_WEIGHTED = "evidence_weighted"

    # Synthesis
    HYPOTHESIS_FORMED = "hypothesis_formed"
    HYPOTHESIS_TESTED = "hypothesis_tested"
    CONFIDENCE_UPDATED = "confidence_updated"

    # Conclusion
    PRELIMINARY_CONCLUSION = "preliminary_conclusion"
    FINAL_DETERMINATION = "final_determination"
    UNCERTAINTY_NOTED = "uncertainty_noted"


class ThinkingStep(BaseModel):
    """
    A single step in the thinking process.

    Task 2.2.1-2.2.3: Define ThinkingStep data class with all required fields.
    """

    # Core fields (Task 2.2.2)
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp when this step occurred",
    )
    step_type: ThinkingStepType = Field(..., description="Type of thinking step")
    content: str = Field(..., description="Description of what happened in this step")

    # Extended fields (Task 2.2.3)
    sources_referenced: list[str] = Field(
        default_factory=list, description="URLs of sources referenced in this step"
    )
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence level at this step (0-1)"
    )

    # Additional context
    agent_id: str | None = Field(None, description="ID of the agent that recorded this step")
    duration_ms: int | None = Field(None, description="Duration of this step in milliseconds")
    metadata: dict = Field(default_factory=dict, description="Additional metadata for this step")

    def to_markdown(self) -> str:
        """Format this step as markdown for readability."""
        lines = [
            f"### {self.step_type.value.replace('_', ' ').title()}",
            f"*{self.timestamp}*",
            "",
            self.content,
        ]

        if self.sources_referenced:
            lines.append("")
            lines.append("**Sources:**")
            for src in self.sources_referenced:
                lines.append(f"- {src}")

        if self.confidence is not None:
            lines.append(f"\n**Confidence:** {self.confidence:.1%}")

        return "\n".join(lines)


class ThinkingRecorder(BaseModel):
    """
    Records and manages the thinking process of an agent.

    Task 2.2.4-2.2.7: Implement ThinkingRecorder class.
    """

    agent_id: str = Field(..., description="ID of the agent being recorded")
    steps: list[ThinkingStep] = Field(default_factory=list, description="List of thinking steps")
    started_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(), description="When recording started"
    )
    completed_at: str | None = Field(None, description="When recording completed")

    def add_step(
        self,
        step_type: ThinkingStepType,
        content: str,
        sources_referenced: list[str] | None = None,
        confidence: float | None = None,
        duration_ms: int | None = None,
        metadata: dict | None = None,
    ) -> ThinkingStep:
        """
        Add a new thinking step.

        Task 2.2.5: Implement add_step() method.

        Args:
            step_type: Type of thinking step
            content: Description of the step
            sources_referenced: URLs referenced in this step
            confidence: Current confidence level
            duration_ms: Duration of this step
            metadata: Additional metadata

        Returns:
            The created ThinkingStep
        """
        step = ThinkingStep(
            step_type=step_type,
            content=content,
            sources_referenced=sources_referenced or [],
            confidence=confidence,
            agent_id=self.agent_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self.steps.append(step)

        logger.debug(
            "Added thinking step",
            agent_id=self.agent_id,
            step_type=step_type.value,
            step_count=len(self.steps),
        )

        return step

    def record_research_start(self, question: str, criteria: str) -> ThinkingStep:
        """Record the start of research."""
        return self.add_step(
            step_type=ThinkingStepType.RESEARCH_START,
            content=f"Starting research on: {question}\nCriteria: {criteria}",
            confidence=0.5,
        )

    def record_source_found(
        self,
        url: str,
        title: str,
        relevance: str,
    ) -> ThinkingStep:
        """Record discovery of a source."""
        return self.add_step(
            step_type=ThinkingStepType.SOURCE_FOUND,
            content=f"Found source: {title}\nRelevance: {relevance}",
            sources_referenced=[url],
        )

    def record_fact_extracted(
        self,
        fact: str,
        source_urls: list[str],
        confidence: float,
    ) -> ThinkingStep:
        """Record extraction of a fact."""
        return self.add_step(
            step_type=ThinkingStepType.FACT_EXTRACTED,
            content=f"Extracted fact: {fact}",
            sources_referenced=source_urls,
            confidence=confidence,
        )

    def record_conclusion(
        self,
        outcome: str,
        reasoning: str,
        confidence: float,
    ) -> ThinkingStep:
        """Record final conclusion."""
        self.completed_at = datetime.utcnow().isoformat()
        return self.add_step(
            step_type=ThinkingStepType.FINAL_DETERMINATION,
            content=f"Conclusion: {outcome}\nReasoning: {reasoning}",
            confidence=confidence,
        )

    def get_summary(self) -> dict:
        """
        Get a summary of the thinking process.

        Task 2.2.6: Implement get_summary() method.

        Returns:
            Dictionary with summary statistics
        """
        if not self.steps:
            return {
                "agent_id": self.agent_id,
                "total_steps": 0,
                "step_types": {},
                "sources_count": 0,
                "duration_total_ms": 0,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
            }

        # Count step types
        step_type_counts: dict[str, int] = {}
        for step in self.steps:
            key = step.step_type.value
            step_type_counts[key] = step_type_counts.get(key, 0) + 1

        # Count unique sources
        all_sources: set[str] = set()
        for step in self.steps:
            all_sources.update(step.sources_referenced)

        # Calculate total duration
        total_duration = sum(step.duration_ms or 0 for step in self.steps)

        # Get confidence progression
        confidence_steps = [
            (step.timestamp, step.confidence) for step in self.steps if step.confidence is not None
        ]

        # Get final confidence
        final_confidence = None
        for step in reversed(self.steps):
            if step.confidence is not None:
                final_confidence = step.confidence
                break

        return {
            "agent_id": self.agent_id,
            "total_steps": len(self.steps),
            "step_types": step_type_counts,
            "sources_count": len(all_sources),
            "unique_sources": list(all_sources),
            "duration_total_ms": total_duration,
            "final_confidence": final_confidence,
            "confidence_progression": confidence_steps,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def to_dict(self) -> dict:
        """
        Serialize the recorder to a dictionary.

        Task 2.2.7: Implement to_dict() serialization method.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "agent_id": self.agent_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [step.model_dump() for step in self.steps],
            "summary": self.get_summary(),
        }

    def to_markdown(self) -> str:
        """Export the thinking process as markdown."""
        lines = [
            f"# Thinking Process: Agent {self.agent_id}",
            "",
            f"**Started:** {self.started_at}",
        ]

        if self.completed_at:
            lines.append(f"**Completed:** {self.completed_at}")

        lines.extend(
            [
                "",
                f"**Total Steps:** {len(self.steps)}",
                "",
                "---",
                "",
            ]
        )

        for i, step in enumerate(self.steps, 1):
            lines.append(f"## Step {i}")
            lines.append(step.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all recorded steps."""
        self.steps = []
        self.started_at = datetime.utcnow().isoformat()
        self.completed_at = None
