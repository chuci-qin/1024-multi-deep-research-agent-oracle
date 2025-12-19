# Contributing to 1024 Multi-Agent Deep Research Oracle

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Git
- A Gemini API key (for testing)

### Development Setup

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/1024-multi-deep-research-agent-oracle.git
cd 1024-multi-deep-research-agent-oracle

# 3. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 4. Install development dependencies
pip install -e ".[dev]"

# 5. Set up pre-commit hooks
pre-commit install

# 6. Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=oracle --cov-report=html

# Run specific test file
pytest tests/test_consensus.py -v
```

## 📝 How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in Issues
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Explain how it fits with the project goals

### Submitting Pull Requests

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow the code style (see below)
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes**:
   ```bash
   # Run tests
   pytest tests/
   
   # Run linter
   ruff check .
   
   # Run type checker
   mypy oracle/
   ```

4. **Commit your changes**:
   ```bash
   git commit -m "feat: add new feature description"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Test changes
   - `refactor:` Code refactoring

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then create a Pull Request on GitHub.

## 🎨 Code Style

### Python Style

We use `ruff` for linting and `black` for formatting:

```bash
# Format code
black oracle/ tests/

# Check linting
ruff check .

# Fix linting issues
ruff check . --fix
```

### Type Hints

All functions should have type hints:

```python
# Good
async def research(
    question: str,
    criteria: str,
    min_sources: int = 50,
) -> AgentResult:
    ...

# Bad
async def research(question, criteria, min_sources=50):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_consensus(
    results: list[AgentResult],
    threshold: float = 0.67,
) -> ConsensusResult:
    """Calculate consensus from agent results.
    
    Args:
        results: List of agent research results.
        threshold: Minimum agreement ratio for consensus.
    
    Returns:
        ConsensusResult with outcome and confidence.
    
    Raises:
        InsufficientAgentsError: If fewer than 3 agents.
    """
    ...
```

## 🏗️ Project Structure

```
1024-multi-deep-research-agent-oracle/
├── oracle/                    # Main package
│   ├── __init__.py
│   ├── agents/               # Agent implementations
│   │   ├── base.py
│   │   ├── gemini.py
│   │   └── openai.py
│   ├── consensus/            # Consensus engine
│   │   ├── engine.py
│   │   └── voting.py
│   ├── storage/              # IPFS storage
│   │   └── ipfs.py
│   └── api/                  # REST API
│       └── server.py
├── tests/                    # Test suite
│   ├── test_agents.py
│   ├── test_consensus.py
│   └── conftest.py
├── docs/                     # Documentation
└── examples/                 # Usage examples
```

## 🧪 Testing Guidelines

### Unit Tests

```python
# tests/test_consensus.py

import pytest
from oracle.consensus import ConsensusEngine, AgentResult

def test_consensus_with_full_agreement():
    """Test consensus when all agents agree."""
    results = [
        AgentResult(agent_id="a", outcome="YES", confidence=0.85),
        AgentResult(agent_id="b", outcome="YES", confidence=0.82),
        AgentResult(agent_id="c", outcome="YES", confidence=0.88),
    ]
    
    engine = ConsensusEngine(threshold=0.67)
    consensus = engine.calculate(results)
    
    assert consensus.reached is True
    assert consensus.outcome == "YES"
    assert consensus.agreement_ratio == 1.0
```

### Integration Tests

```python
# tests/integration/test_gemini_agent.py

import pytest
from oracle.agents import GeminiDeepResearchAgent

@pytest.mark.integration
@pytest.mark.asyncio
async def test_gemini_agent_research():
    """Test Gemini agent can complete research."""
    agent = GeminiDeepResearchAgent(min_sources=10)  # Lower for testing
    
    result = await agent.research(
        question="What is the capital of France?",
        criteria="The official capital city",
    )
    
    assert result.outcome in ["YES", "NO", "UNDETERMINED"]
    assert len(result.sources) >= 10
```

### Mocking External APIs

```python
# tests/conftest.py

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "candidates": [{
            "content": {"parts": [{"text": "OUTCOME: YES\nConfidence: 85%"}]},
            "grounding_metadata": {
                "grounding_chunks": [
                    {"web": {"uri": "https://example.com", "title": "Example"}}
                ]
            }
        }]
    }
```

## 📚 Documentation

### Where to Document

- **Code**: Docstrings for all public functions
- **README.md**: High-level overview and quick start
- **docs/**: Detailed guides and architecture

### Building Docs

```bash
# Install docs dependencies
pip install mkdocs mkdocs-material

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

## 🏷️ Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature request |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `question` | Further information requested |

## 📋 Pull Request Checklist

- [ ] Code follows project style
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] All tests passing
- [ ] Linting passing
- [ ] PR description explains changes

## 🙏 Thank You!

Your contributions make this project better. If you have questions, feel free to:

- Open an issue
- Join our [Discord](https://discord.gg/1024chain)
- Reach out on [Twitter](https://twitter.com/1024chain)
