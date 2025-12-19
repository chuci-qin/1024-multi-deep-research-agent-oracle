"""
Gemini Deep Research Agent

Uses Google Gemini API with Google Search grounding to collect
50+ sources and provide structured research results.
"""

import asyncio
import json
import os
import time
from typing import Optional
from urllib.parse import urlparse

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import structlog

from oracle.agents.base import BaseAgent, SearchStrategy, AgentConfig
from oracle.models import AgentResult, ResearchSource, Outcome, SourceCategory

logger = structlog.get_logger()


class GeminiDeepResearchAgent(BaseAgent):
    """
    Deep Research Agent powered by Google Gemini API.
    
    Uses Google Search grounding to collect 50+ sources
    and returns structured results with full citations.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp",
        agent_id: Optional[str] = None,
        strategy: SearchStrategy = SearchStrategy.COMPREHENSIVE,
        config: Optional[AgentConfig] = None,
    ):
        super().__init__(agent_id, strategy, config)
        
        # Configure Gemini API
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._api_key = api_key
        self._model_name = model
        self._initialized = False
        self.model = None
        
        # Try to initialize, but don't fail startup
        if api_key:
            try:
                genai.configure(api_key=api_key)
                # Note: Google Search grounding is automatically available in Gemini 2.0
                # The model will search the web as needed based on the prompt
                self.model = genai.GenerativeModel(model_name=model)
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
        deadline: Optional[str] = None,
    ) -> AgentResult:
        """
        Conduct deep research using Gemini with Google Search grounding.
        """
        start_time = time.time()
        
        logger.info(
            "Starting research",
            agent_id=self.agent_id,
            question=question[:100],
        )
        
        try:
            # Build research prompt
            prompt = self._build_research_prompt(question, resolution_criteria, deadline)
            
            # Generate response with search grounding
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=GenerationConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens,
                ),
            )
            
            # Extract sources from grounding metadata
            sources = self._extract_sources(response)
            
            # If not enough sources, do additional research
            if len(sources) < self.config.min_sources:
                logger.info(
                    "Expanding research for more sources",
                    current_sources=len(sources),
                    required=self.config.min_sources,
                )
                additional_sources = await self._expand_research(question, sources)
                sources.extend(additional_sources)
            
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
        deadline: Optional[str] = None,
    ) -> str:
        """Build the research prompt for Gemini."""
        deadline_text = f"\nDeadline: {deadline}" if deadline else ""
        
        return f"""You are a Deep Research Agent for a prediction market oracle.
Your task is to comprehensively research whether an event has occurred or will occur.

## QUESTION
{question}

## RESOLUTION CRITERIA
{resolution_criteria}{deadline_text}

## INSTRUCTIONS

1. **Search Comprehensively**: Use Google Search to find at least 50 diverse sources
2. **Source Categories**: Include sources from ALL of these categories:
   - **Official sources** (5+): Government sites (.gov), company websites, press releases
   - **News sources** (15+): Reuters, AP, Bloomberg, BBC, CNN, major newspapers
   - **Social media** (10+): Verified Twitter/X accounts, Reddit discussions
   - **Domain-specific** (10+): Industry publications, specialized sites
   - **Fact-checking** (3+): Snopes, PolitiFact, FactCheck.org

3. **Analyze Evidence**: 
   - What do official sources say?
   - What does news coverage report?
   - Is there consensus across sources?
   - Are there any contradictions?

4. **Determine Outcome**:
   - **YES**: The event clearly occurred/will occur based on evidence
   - **NO**: The event clearly did not occur/will not occur based on evidence
   - **UNDETERMINED**: Insufficient or conflicting evidence

5. **Format Your Response**:

OUTCOME: [YES/NO/UNDETERMINED]
CONFIDENCE: [0-100]%

REASONING:
[Your detailed analysis with references to specific sources]

KEY EVIDENCE:
1. [Key finding from Source 1]
2. [Key finding from Source 2]
3. [Key finding from Source 3]
...

CONTRADICTIONS (if any):
[Note any conflicting information found]
"""
    
    def _extract_sources(self, response) -> list[ResearchSource]:
        """Extract sources from Gemini's groundingMetadata."""
        sources: list[ResearchSource] = []
        
        if not hasattr(response, 'candidates') or not response.candidates:
            logger.warning("No candidates in response")
            return sources
        
        candidate = response.candidates[0]
        
        if not hasattr(candidate, 'grounding_metadata'):
            logger.warning("No grounding metadata in response")
            return sources
        
        metadata = candidate.grounding_metadata
        
        # Extract grounding chunks (source URLs)
        if hasattr(metadata, 'grounding_chunks'):
            for chunk in metadata.grounding_chunks:
                if hasattr(chunk, 'web'):
                    url = chunk.web.uri
                    title = chunk.web.title if hasattr(chunk.web, 'title') else ""
                    
                    source = ResearchSource(
                        url=url,
                        title=title,
                        snippet="",
                        category=self._categorize_url(url),
                        relevance_score=0.8,
                        credibility_score=self._calculate_credibility(url),
                        cited_by=[self.agent_id],
                    )
                    
                    # Avoid duplicates
                    if source not in sources:
                        sources.append(source)
        
        # Extract snippets from grounding supports if available
        if hasattr(metadata, 'grounding_supports'):
            for support in metadata.grounding_supports:
                if hasattr(support, 'segment') and hasattr(support.segment, 'text'):
                    snippet_text = support.segment.text
                    
                    # Map snippet to sources
                    if hasattr(support, 'grounding_chunk_indices'):
                        for idx in support.grounding_chunk_indices:
                            if idx < len(sources) and not sources[idx].snippet:
                                sources[idx].snippet = snippet_text[:500]
        
        logger.info(f"Extracted {len(sources)} sources from grounding metadata")
        return sources
    
    def _categorize_url(self, url: str) -> SourceCategory:
        """Categorize a URL into source category."""
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            return SourceCategory.DOMAIN_SPECIFIC
        
        # Official sources
        if any(tld in domain for tld in ['.gov', '.edu', '.mil']):
            return SourceCategory.OFFICIAL
        
        # Company official sites (heuristic)
        official_patterns = ['newsroom', 'press', 'investor', 'about', 'corporate']
        if any(pattern in url.lower() for pattern in official_patterns):
            return SourceCategory.OFFICIAL
        
        # Major news sources
        news_domains = [
            'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
            'bloomberg.com', 'cnn.com', 'nytimes.com', 'wsj.com',
            'theguardian.com', 'washingtonpost.com', 'forbes.com',
            'ft.com', 'economist.com', 'usatoday.com', 'nbcnews.com',
            'cbsnews.com', 'abcnews.go.com', 'foxnews.com', 'politico.com',
            'axios.com', 'thehill.com', 'npr.org', 'pbs.org',
        ]
        if any(news in domain for news in news_domains):
            return SourceCategory.NEWS
        
        # Social media
        social_domains = [
            'twitter.com', 'x.com', 'reddit.com', 'facebook.com',
            'linkedin.com', 'youtube.com', 'instagram.com', 'tiktok.com',
            'threads.net', 'mastodon',
        ]
        if any(social in domain for social in social_domains):
            return SourceCategory.SOCIAL
        
        # Fact-check sources
        factcheck_domains = [
            'snopes.com', 'politifact.com', 'factcheck.org',
            'fullfact.org', 'leadstories.com', 'checkyourfact.com',
        ]
        if any(fc in domain for fc in factcheck_domains):
            return SourceCategory.FACT_CHECK
        
        # Default to domain-specific
        return SourceCategory.DOMAIN_SPECIFIC
    
    def _calculate_credibility(self, url: str) -> float:
        """Calculate credibility score based on domain."""
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            return 0.5
        
        # High credibility (0.9+)
        high_cred = [
            '.gov', '.edu', 'reuters.com', 'apnews.com', 'bbc.com',
            'bloomberg.com', 'wsj.com', 'ft.com', 'economist.com',
        ]
        if any(hc in domain for hc in high_cred):
            return 0.95
        
        # Good credibility (0.8+)
        good_cred = [
            'nytimes.com', 'washingtonpost.com', 'theguardian.com',
            'cnn.com', 'forbes.com', 'politico.com', 'npr.org',
        ]
        if any(gc in domain for gc in good_cred):
            return 0.85
        
        # Moderate credibility (0.7+)
        moderate_cred = [
            'twitter.com', 'x.com', 'reddit.com', 'youtube.com',
        ]
        if any(mc in domain for mc in moderate_cred):
            return 0.70
        
        # Default
        return 0.75
    
    def _parse_response(self, response) -> tuple[Outcome, float, str]:
        """Parse outcome, confidence, and reasoning from response."""
        if not response.candidates:
            return Outcome.UNDETERMINED, 0.0, "No response generated"
        
        text = response.text
        
        # Parse outcome
        outcome = Outcome.UNDETERMINED
        if "OUTCOME: YES" in text.upper() or "OUTCOME:YES" in text.upper():
            outcome = Outcome.YES
        elif "OUTCOME: NO" in text.upper() or "OUTCOME:NO" in text.upper():
            outcome = Outcome.NO
        
        # Parse confidence
        confidence = 0.5
        import re
        conf_match = re.search(r'CONFIDENCE:\s*(\d+(?:\.\d+)?)\s*%?', text, re.IGNORECASE)
        if conf_match:
            try:
                conf_value = float(conf_match.group(1))
                # Normalize to 0-1 if given as percentage
                confidence = conf_value / 100 if conf_value > 1 else conf_value
            except ValueError:
                pass
        
        # Extract reasoning
        reasoning = text
        reasoning_match = re.search(r'REASONING:\s*(.*?)(?=KEY EVIDENCE:|CONTRADICTIONS:|$)', text, re.DOTALL | re.IGNORECASE)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        
        return outcome, confidence, reasoning
    
    async def _expand_research(
        self,
        question: str,
        existing_sources: list[ResearchSource],
    ) -> list[ResearchSource]:
        """Conduct additional research to gather more sources."""
        additional_sources: list[ResearchSource] = []
        
        # Generate additional queries
        additional_queries = [
            f"{question} news today",
            f"{question} official report",
            f"{question} analysis",
            f"{question} twitter reaction",
            f"{question} reddit discussion",
        ]
        
        for query in additional_queries:
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    f"Search for: {query}\n\nProvide a brief summary of what you find.",
                    generation_config=GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                    ),
                )
                
                new_sources = self._extract_sources(response)
                
                # Add sources not already in existing
                existing_urls = {s.url for s in existing_sources}
                for source in new_sources:
                    if source.url not in existing_urls:
                        additional_sources.append(source)
                        existing_urls.add(source.url)
                
            except Exception as e:
                logger.warning(f"Additional query failed: {e}")
                continue
            
            # Check if we have enough
            total = len(existing_sources) + len(additional_sources)
            if total >= self.config.min_sources:
                break
        
        logger.info(f"Found {len(additional_sources)} additional sources")
        return additional_sources
