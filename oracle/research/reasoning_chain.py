"""
Reasoning Chain Recorder

Records the logical reasoning chain that leads to the final determination.
This provides a transparent audit trail of how conclusions were reached.

Task ID: 2.4.1 - 2.4.7 from IMPLEMENTATION-TRACKER.md
"""

from datetime import datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ReasoningStepType(str, Enum):
    """Types of reasoning steps."""

    # Task 2.4.4: Observation type
    OBSERVATION = "observation"  # Raw observation from sources

    # Task 2.4.5: Synthesis type
    SYNTHESIS = "synthesis"  # Combining multiple observations

    # Task 2.4.6: Conclusion type
    CONCLUSION = "conclusion"  # Final or intermediate conclusion

    # Additional types
    ASSUMPTION = "assumption"  # Stated assumptions
    INFERENCE = "inference"  # Logical inference
    CONTRADICTION = "contradiction"  # Identified contradictions
    UNCERTAINTY = "uncertainty"  # Areas of uncertainty
    WEIGHT_EVIDENCE = "weight_evidence"  # Weighing evidence


class ReasoningStep(BaseModel):
    """
    A single step in the reasoning chain.

    Task 2.4.1-2.4.2: Define ReasoningStep data class.
    """

    # Core fields (Task 2.4.2)
    step_type: ReasoningStepType = Field(..., description="Type of reasoning step")
    content: str = Field(..., description="The reasoning content")
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Evidence supporting this step (URLs or facts)"
    )

    # Sequence information
    step_number: int = Field(default=0, description="Order in the reasoning chain")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When this step was recorded",
    )

    # Analysis metadata
    confidence_impact: float | None = Field(
        None, ge=-1.0, le=1.0, description="How this step affects confidence (-1 to +1)"
    )
    outcome_support: str | None = Field(
        None, description="Which outcome this evidence supports (YES/NO/UNDETERMINED)"
    )

    def to_markdown(self) -> str:
        """Format this step as markdown."""
        icon = {
            ReasoningStepType.OBSERVATION: "👁️",
            ReasoningStepType.SYNTHESIS: "🔗",
            ReasoningStepType.CONCLUSION: "✅",
            ReasoningStepType.ASSUMPTION: "💭",
            ReasoningStepType.INFERENCE: "🔍",
            ReasoningStepType.CONTRADICTION: "⚠️",
            ReasoningStepType.UNCERTAINTY: "❓",
            ReasoningStepType.WEIGHT_EVIDENCE: "⚖️",
        }.get(self.step_type, "•")

        lines = [
            f"{icon} **{self.step_type.value.replace('_', ' ').title()}** (Step {self.step_number})",
            "",
            self.content,
        ]

        if self.supporting_evidence:
            lines.append("")
            lines.append("*Evidence:*")
            for ev in self.supporting_evidence[:5]:  # Limit displayed
                lines.append(f"  - {ev[:100]}...")

        if self.outcome_support:
            lines.append(f"\n*Supports:* {self.outcome_support}")

        if self.confidence_impact is not None:
            impact_str = (
                f"+{self.confidence_impact:.2f}"
                if self.confidence_impact > 0
                else f"{self.confidence_impact:.2f}"
            )
            lines.append(f"*Confidence Impact:* {impact_str}")

        return "\n".join(lines)


class ReasoningChain(BaseModel):
    """
    Complete reasoning chain from observations to conclusion.

    Task 2.4.3-2.4.7: Implement ReasoningChain class.
    """

    agent_id: str = Field(..., description="ID of the reasoning agent")
    question: str = Field(default="", description="The question being resolved")
    steps: list[ReasoningStep] = Field(
        default_factory=list, description="Steps in the reasoning chain"
    )
    final_outcome: str | None = Field(None, description="Final determined outcome")
    final_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Final confidence level"
    )
    started_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(), description="When reasoning started"
    )
    completed_at: str | None = Field(None, description="When reasoning completed")

    def _next_step_number(self) -> int:
        """Get the next step number."""
        return len(self.steps) + 1

    def add_observation(
        self,
        observation: str,
        sources: list[str] | None = None,
        outcome_support: str | None = None,
        confidence_impact: float | None = None,
    ) -> ReasoningStep:
        """
        Add an observation from research.

        Task 2.4.4: Support observation type.
        """
        step = ReasoningStep(
            step_type=ReasoningStepType.OBSERVATION,
            content=observation,
            supporting_evidence=sources or [],
            step_number=self._next_step_number(),
            outcome_support=outcome_support,
            confidence_impact=confidence_impact,
        )
        self.steps.append(step)

        logger.debug(
            "Added observation",
            agent_id=self.agent_id,
            step_number=step.step_number,
        )

        return step

    def add_synthesis(
        self,
        synthesis: str,
        based_on: list[str] | None = None,
        outcome_support: str | None = None,
        confidence_impact: float | None = None,
    ) -> ReasoningStep:
        """
        Add a synthesis combining multiple observations.

        Task 2.4.5: Support synthesis type.
        """
        step = ReasoningStep(
            step_type=ReasoningStepType.SYNTHESIS,
            content=synthesis,
            supporting_evidence=based_on or [],
            step_number=self._next_step_number(),
            outcome_support=outcome_support,
            confidence_impact=confidence_impact,
        )
        self.steps.append(step)

        logger.debug(
            "Added synthesis",
            agent_id=self.agent_id,
            step_number=step.step_number,
        )

        return step

    def add_conclusion(
        self,
        conclusion: str,
        outcome: str,
        confidence: float,
        supporting_evidence: list[str] | None = None,
    ) -> ReasoningStep:
        """
        Add a conclusion.

        Task 2.4.6: Support conclusion type.
        """
        step = ReasoningStep(
            step_type=ReasoningStepType.CONCLUSION,
            content=conclusion,
            supporting_evidence=supporting_evidence or [],
            step_number=self._next_step_number(),
            outcome_support=outcome,
            confidence_impact=None,  # Conclusion doesn't impact, it summarizes
        )
        self.steps.append(step)

        # If this is the final conclusion, record it
        self.final_outcome = outcome
        self.final_confidence = confidence
        self.completed_at = datetime.utcnow().isoformat()

        logger.info(
            "Reasoning concluded",
            agent_id=self.agent_id,
            outcome=outcome,
            confidence=confidence,
            total_steps=len(self.steps),
        )

        return step

    def add_step(
        self,
        step_type: ReasoningStepType,
        content: str,
        supporting_evidence: list[str] | None = None,
        outcome_support: str | None = None,
        confidence_impact: float | None = None,
    ) -> ReasoningStep:
        """Add a generic reasoning step."""
        step = ReasoningStep(
            step_type=step_type,
            content=content,
            supporting_evidence=supporting_evidence or [],
            step_number=self._next_step_number(),
            outcome_support=outcome_support,
            confidence_impact=confidence_impact,
        )
        self.steps.append(step)
        return step

    def add_contradiction(
        self,
        description: str,
        conflicting_sources: list[str],
    ) -> ReasoningStep:
        """Record a detected contradiction in the evidence."""
        return self.add_step(
            step_type=ReasoningStepType.CONTRADICTION,
            content=description,
            supporting_evidence=conflicting_sources,
            confidence_impact=-0.1,  # Contradictions reduce confidence
        )

    def add_uncertainty(
        self,
        description: str,
        reason: str,
    ) -> ReasoningStep:
        """Record an area of uncertainty."""
        return self.add_step(
            step_type=ReasoningStepType.UNCERTAINTY,
            content=f"{description}. Reason: {reason}",
            confidence_impact=-0.05,
        )

    def get_observations(self) -> list[ReasoningStep]:
        """Get all observation steps."""
        return [s for s in self.steps if s.step_type == ReasoningStepType.OBSERVATION]

    def get_evidence_for(self, outcome: str) -> list[ReasoningStep]:
        """Get all steps supporting a specific outcome."""
        return [s for s in self.steps if s.outcome_support == outcome]

    def calculate_evidence_balance(self) -> dict:
        """Calculate the balance of evidence for each outcome."""
        balance: dict[str, float] = {"YES": 0.0, "NO": 0.0, "UNDETERMINED": 0.0}

        for step in self.steps:
            if step.outcome_support and step.confidence_impact:
                outcome = step.outcome_support.upper()
                if outcome in balance:
                    balance[outcome] += step.confidence_impact

        return balance

    def to_markdown(self) -> str:
        """
        Export the reasoning chain as markdown.

        Task 2.4.7: Implement to_markdown() method.
        """
        lines = [
            f"# Reasoning Chain: Agent {self.agent_id}",
            "",
            f"**Question:** {self.question}" if self.question else "",
            f"**Started:** {self.started_at}",
        ]

        if self.completed_at:
            lines.append(f"**Completed:** {self.completed_at}")

        if self.final_outcome:
            lines.extend(
                [
                    "",
                    "## Final Determination",
                    f"**Outcome:** {self.final_outcome}",
                    f"**Confidence:** {self.final_confidence:.1%}" if self.final_confidence else "",
                ]
            )

        lines.extend(
            [
                "",
                "---",
                "",
                "## Reasoning Steps",
                "",
            ]
        )

        for step in self.steps:
            lines.append(step.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")

        # Evidence balance
        balance = self.calculate_evidence_balance()
        lines.extend(
            [
                "## Evidence Balance",
                "",
                f"- YES: {balance['YES']:+.2f}",
                f"- NO: {balance['NO']:+.2f}",
                f"- UNDETERMINED: {balance['UNDETERMINED']:+.2f}",
            ]
        )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize the reasoning chain to dictionary."""
        return {
            "agent_id": self.agent_id,
            "question": self.question,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "final_outcome": self.final_outcome,
            "final_confidence": self.final_confidence,
            "steps": [s.model_dump() for s in self.steps],
            "evidence_balance": self.calculate_evidence_balance(),
            "total_steps": len(self.steps),
        }

    def clear(self) -> None:
        """Clear the reasoning chain."""
        self.steps = []
        self.final_outcome = None
        self.final_confidence = None
        self.started_at = datetime.utcnow().isoformat()
        self.completed_at = None
