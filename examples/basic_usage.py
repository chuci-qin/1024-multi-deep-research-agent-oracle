#!/usr/bin/env python3
"""
Basic usage example for Multi-Agent Oracle.

This example shows how to use the oracle to resolve a prediction market question.

Requirements:
    - Set GEMINI_API_KEY environment variable

Usage:
    python examples/basic_usage.py
"""

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from oracle import MultiAgentOracle
from oracle.agents import GeminiDeepResearchAgent, SearchStrategy
from oracle.core import OracleConfig


async def main():
    """Run a basic oracle resolution."""

    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("   Set it with: export GEMINI_API_KEY=your_key_here")
        return

    print("🔮 1024 Multi-Agent Deep Research Oracle")
    print("=" * 50)

    # Define the question to resolve
    question = "Did Bitcoin reach $100,000 by December 2025?"
    resolution_criteria = """
    The Bitcoin (BTC) price must have reached or exceeded $100,000.00 USD 
    on at least one major cryptocurrency exchange (Coinbase, Binance, Kraken) 
    at any point before midnight UTC on December 31, 2025.
    """

    print(f"\n📋 Question: {question}")
    print(f"📏 Criteria: {resolution_criteria.strip()}")
    print()

    # Initialize oracle with 3 agents using different strategies
    print("🚀 Initializing oracle with 3 agents...")

    oracle = MultiAgentOracle(
        agents=[
            GeminiDeepResearchAgent(
                agent_id="gemini-comprehensive",
                strategy=SearchStrategy.COMPREHENSIVE,
            ),
            GeminiDeepResearchAgent(
                agent_id="gemini-focused",
                strategy=SearchStrategy.FOCUSED,
            ),
            GeminiDeepResearchAgent(
                agent_id="gemini-diverse",
                strategy=SearchStrategy.DIVERSE,
            ),
        ],
        config=OracleConfig(
            consensus_threshold=0.67,
            enable_ipfs=True,
        ),
    )

    print("🔍 Running agent research (this may take 1-2 minutes)...")
    print()

    # Resolve the question
    try:
        result = await oracle.resolve(
            question=question,
            resolution_criteria=resolution_criteria,
            market_id=12345,
        )

        # Display results
        print("=" * 50)
        print("📊 RESULTS")
        print("=" * 50)

        if result.consensus.reached:
            print("✅ Consensus Reached!")
        else:
            print("⚠️ No Consensus (requires human review)")

        print(f"\n🎯 Outcome: {result.consensus.outcome.value}")
        print(f"📈 Confidence: {result.consensus.confidence:.1%}")
        print(f"🤝 Agreement: {result.consensus.agreement_ratio:.0%}")
        print(f"📚 Total Sources: {len(result.merged_sources)}")

        if result.ipfs_cid:
            print(f"🔗 IPFS Hash: {result.ipfs_cid}")

        # Agent breakdown
        print("\n👥 Agent Results:")
        for agent_result in result.agent_results:
            status = "✓" if agent_result.error is None else "✗"
            print(
                f"   {status} {agent_result.agent_id}: "
                f"{agent_result.outcome.value} "
                f"({agent_result.confidence:.0%}, {len(agent_result.sources)} sources)"
            )

        # Top sources
        if result.merged_sources:
            print("\n📰 Top Sources:")
            for i, source in enumerate(result.merged_sources[:5], 1):
                print(f"   {i}. {source.title[:60]}...")
                print(f"      URL: {source.url}")
                print(f"      Category: {source.category.value}")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await oracle.close()

    print("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main())
