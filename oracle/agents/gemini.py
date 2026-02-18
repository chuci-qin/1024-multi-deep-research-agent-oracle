"""
Gemini Deep Research Agent

Uses Google Gemini API with Google Search grounding to collect
sources and provide structured research results.
"""

import asyncio
import json
import os
import time
from urllib.parse import urlparse

import structlog
from google import genai  # New SDK

from oracle.agents.base import AgentConfig, BaseAgent, SearchStrategy
from oracle.models import AgentResult, Outcome, ResearchSource, SourceCategory

logger = structlog.get_logger()


class GeminiDeepResearchAgent(BaseAgent):
    """
    Deep Research Agent powered by Google Gemini API.

    Uses Google Search grounding to collect sources
    and returns structured results with full citations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        agent_id: str | None = None,
        strategy: SearchStrategy = SearchStrategy.COMPREHENSIVE,
        config: AgentConfig | None = None,
    ):
        super().__init__(agent_id, strategy, config)

        # Configure Gemini API
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._api_key = api_key
        self._model_name = model
        self._initialized = False
        self.client = None

        # Try to initialize
        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
                self._initialized = True
                logger.info(
                    "Initialized Gemini agent",
                    agent_id=self.agent_id,
                    model=model,
                    strategy=strategy.value,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini agent: {e}")
        else:
            logger.warning(
                "GEMINI_API_KEY not set - agent will fail on research calls",
                agent_id=self.agent_id,
            )

    @property
    def model_name(self) -> str:
        return self._model_name

    async def research(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> AgentResult:
        """
        Conduct deep research using Gemini with Google Search grounding.
        """
        start_time = time.time()

        if not self._initialized or not self.client:
            return AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=Outcome.INVALID,
                confidence=0.0,
                reasoning="Agent not initialized - missing API key",
                sources=[],
                research_duration_seconds=0,
                error="GEMINI_API_KEY not configured",
            )

        logger.info(
            "Starting research",
            agent_id=self.agent_id,
            question=question[:100],
        )

        try:
            # Build research prompt
            prompt = self._build_research_prompt(question, resolution_criteria, deadline)

            # Generate response with Google Search grounding
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self._model_name,
                contents=prompt,
                config={
                    "tools": [{"google_search": {}}],
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_tokens,
                },
            )

            # Extract sources from grounding metadata
            sources = self._extract_sources(response)

            # Parse outcome and confidence from response
            outcome, confidence, reasoning = self._parse_response(response)

            duration = time.time() - start_time

            result = AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=outcome,
                confidence=confidence,
                reasoning=reasoning,
                sources=sources,
                research_duration_seconds=duration,
            )

            logger.info(
                "Research completed",
                agent_id=self.agent_id,
                outcome=outcome.value,
                confidence=confidence,
                source_count=len(sources),
                duration=f"{duration:.2f}s",
            )

            return result

        except Exception as e:
            logger.error(
                "Research failed",
                agent_id=self.agent_id,
                error=str(e),
            )

            return AgentResult(
                agent_id=self.agent_id,
                model=self.model_name,
                strategy=self.strategy.value,
                outcome=Outcome.INVALID,
                confidence=0.0,
                reasoning="Research failed due to error",
                sources=[],
                research_duration_seconds=time.time() - start_time,
                error=str(e),
            )

    def _build_research_prompt(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> str:
        """Build the research prompt for Gemini."""
        deadline_block = ""
        if deadline:
            deadline_block = f"""
RESOLUTION TIMESTAMP (CRITICAL): {deadline}

*** TIME PRECISION REQUIREMENT ***
This prediction market resolves at the EXACT timestamp above. You MUST:
1. Find data for this SPECIFIC moment in time — NOT "current" or "latest" data.
2. Even a 1-minute difference is unacceptable. A price at 3:01 PM is NOT valid for a 3:00 PM resolution.
3. Use time-sensitive data sources that provide historical minute-level or second-level data:
   - Exchange APIs (Binance, Coinbase) with timestamp-specific candle data
   - TradingView with exact time markers
   - CoinGecko/CoinMarketCap historical snapshots
   - Bloomberg/Reuters timestamped price feeds
4. If you cannot find data for this EXACT timestamp, state that clearly and use UNDETERMINED.
5. Cross-reference at least 2 independent sources for the same timestamp.
"""

        strategy_instruction = {
            SearchStrategy.COMPREHENSIVE: """
Search comprehensively across multiple source types, with emphasis on timestamped data:
- Official sources (government, company announcements) with publication timestamps
- Major news outlets (Reuters, AP, Bloomberg, BBC) with article timestamps
- Financial data sources (CoinGecko, TradingView, CoinMarketCap) with exact time markers
- Exchange price feeds (Binance, Coinbase, Kraken) with minute-level candle data
- Expert analysis and reports with publication dates
""",
            SearchStrategy.FOCUSED: """
Focus on the most authoritative and time-precise sources:
- Official announcements and data with publication timestamps
- Primary exchange data (Binance BTC/USDT, Coinbase BTC-USD) with exact timestamps
- Primary news sources (Reuters, AP, Bloomberg) with article timestamps
- Verified factual data with temporal precision
""",
            SearchStrategy.DIVERSE: """
Gather diverse perspectives from different source types, all with timestamps:
- News from different regions and time zones
- Multiple exchanges (cross-verify prices at exact timestamps)
- Social media discussions with post timestamps
- Expert opinions and community forums
- On-chain data and blockchain explorers
""",
        }.get(self.strategy, "Search for relevant information with exact timestamps.")

        return f"""You are an AI oracle for a prediction market. Your task is to research and determine the outcome of a question based on VERIFIABLE, TIME-SPECIFIC evidence.

QUESTION: {question}

RESOLUTION CRITERIA: {resolution_criteria}
{deadline_block}
RESEARCH INSTRUCTIONS:
{strategy_instruction}

Search the web thoroughly using Google Search. Gather evidence from multiple sources.
For price-based or time-sensitive markets, you MUST find data at the exact resolution timestamp.
Do NOT use "current" prices — find the HISTORICAL price at the specified resolution moment.

After researching, provide your determination in the following JSON format:

```json
{{
    "outcome": "YES" or "NO" or "UNDETERMINED",
    "confidence": 0.0 to 1.0,
    "reasoning": "Your detailed reasoning with exact timestamps and source URLs",
    "key_facts": ["fact1 (source, timestamp)", "fact2 (source, timestamp)", "fact3 (source, timestamp)"]
}}
```

Be precise and base your answer on factual evidence from your search results.
If you cannot find data for the EXACT resolution timestamp, use "UNDETERMINED" — do NOT guess.
"""

    def _extract_sources(self, response) -> list[ResearchSource]:
        """Extract sources from Gemini response grounding metadata."""
        sources = []

        try:
            if not hasattr(response, "candidates") or not response.candidates:
                return sources

            candidate = response.candidates[0]

            if not hasattr(candidate, "grounding_metadata") or not candidate.grounding_metadata:
                logger.info("No grounding metadata in response")
                return sources

            gm = candidate.grounding_metadata

            # Extract grounding chunks (sources)
            if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if hasattr(chunk, "web") and chunk.web:
                        web = chunk.web
                        url = getattr(web, "uri", "") or ""
                        title = getattr(web, "title", "") or "Untitled"

                        if url:
                            source = ResearchSource(
                                url=url,
                                title=title,
                                snippet="",
                                category=self._categorize_url(url),
                                credibility_score=self._estimate_credibility(url),
                                cited_by=[self.agent_id],
                            )
                            sources.append(source)

            logger.info(f"Extracted {len(sources)} sources from grounding metadata")

        except Exception as e:
            logger.warning(f"Error extracting sources: {e}")

        return sources

    def _categorize_url(self, url: str) -> SourceCategory:
        """Categorize a URL into source type."""
        domain = urlparse(url).netloc.lower()

        # Official sources
        if any(x in domain for x in [".gov", "sec.gov", "treasury", "federal"]):
            return SourceCategory.OFFICIAL

        # Major news
        news_domains = [
            "reuters",
            "apnews",
            "bloomberg",
            "bbc",
            "cnn",
            "nytimes",
            "wsj",
            "ft.com",
            "cnbc",
            "forbes",
        ]
        if any(x in domain for x in news_domains):
            return SourceCategory.NEWS

        # Crypto/finance specific
        crypto_domains = [
            "coindesk",
            "cointelegraph",
            "coingecko",
            "coinmarketcap",
            "binance",
            "coinbase",
            "investopedia",
            "tradingview",
        ]
        if any(x in domain for x in crypto_domains):
            return SourceCategory.DOMAIN_SPECIFIC

        # Social
        if any(x in domain for x in ["twitter", "x.com", "reddit", "discord"]):
            return SourceCategory.SOCIAL

        # Fact check
        if any(x in domain for x in ["snopes", "factcheck", "politifact"]):
            return SourceCategory.FACT_CHECK

        return SourceCategory.DOMAIN_SPECIFIC

    def _estimate_credibility(self, url: str) -> float:
        """Estimate credibility score for a URL."""
        domain = urlparse(url).netloc.lower()

        high_cred = [".gov", "reuters", "apnews", "bloomberg", "bbc", "wikipedia"]
        medium_cred = ["coindesk", "cointelegraph", "investopedia", "forbes", "cnbc"]

        if any(x in domain for x in high_cred):
            return 0.9
        elif any(x in domain for x in medium_cred):
            return 0.7
        else:
            return 0.5

    def _parse_response(self, response) -> tuple[Outcome, float, str]:
        """Parse the Gemini response to extract outcome, confidence, and reasoning."""
        try:
            text = response.text if response.text else ""

            # Try to extract JSON from response
            json_match = None
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    json_match = text[start:end].strip()
            elif "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                json_match = text[start:end]

            if json_match:
                try:
                    data = json.loads(json_match)

                    outcome_str = data.get("outcome", "UNDETERMINED").upper()
                    if outcome_str == "YES":
                        outcome = Outcome.YES
                    elif outcome_str == "NO":
                        outcome = Outcome.NO
                    else:
                        outcome = Outcome.UNDETERMINED

                    confidence = float(data.get("confidence", 0.5))
                    reasoning = data.get("reasoning", text[:500])

                    return outcome, confidence, reasoning
                except json.JSONDecodeError:
                    pass

            # Fallback: parse from text
            text_lower = text.lower()

            if "yes" in text_lower and "no" not in text_lower[:100]:
                outcome = Outcome.YES
                confidence = 0.7
            elif "no" in text_lower and "yes" not in text_lower[:100]:
                outcome = Outcome.NO
                confidence = 0.7
            else:
                outcome = Outcome.UNDETERMINED
                confidence = 0.5

            return outcome, confidence, text[:500]

        except Exception as e:
            logger.warning(f"Error parsing response: {e}")
            return Outcome.UNDETERMINED, 0.0, str(e)

    async def close(self):
        """Cleanup resources."""
        pass
