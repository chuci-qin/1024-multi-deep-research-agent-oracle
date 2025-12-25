"""
Research Process Recording Module.

Components for recording and tracking the AI agent's research process,
including thinking steps, website visits, and reasoning chains.

This module provides transparency and verifiability for the oracle's
decision-making process.
"""

from oracle.research.thinking_recorder import (
    ThinkingStep,
    ThinkingStepType,
    ThinkingRecorder,
)
from oracle.research.website_tracker import (
    WebsiteVisit,
    WebsiteTracker,
    CredibilityTier,
)
from oracle.research.reasoning_chain import (
    ReasoningStep,
    ReasoningStepType,
    ReasoningChain,
)

__all__ = [
    # Thinking Recorder
    "ThinkingStep",
    "ThinkingStepType",
    "ThinkingRecorder",
    # Website Tracker
    "WebsiteVisit",
    "WebsiteTracker",
    "CredibilityTier",
    # Reasoning Chain
    "ReasoningStep",
    "ReasoningStepType",
    "ReasoningChain",
]

