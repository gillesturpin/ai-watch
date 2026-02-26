# AI Watch

Autonomous agent that produces a daily AI briefing from 3 sources: HuggingFace Papers, GitHub Trending, and Simon Willison.

Runs every morning via GitHub Actions. Fetches, filters, enriches, summarizes. Not a one-shot notebook — a system that produces a fresh result every day.

## How It Works

```
HuggingFace Papers API ---+
GitHub Trending (scrape) --+-- Top 3 per source -- LLM Agent + Tools -- Markdown Briefing
Simon Willison RSS --------+
```

The agent decides for each item whether it needs more context:
- Paper mentions a model -> searches HF Hub (downloads, license)
- Vague GitHub description -> reads the README
- Simon post with just a title -> fetches the full content

## Quick Start

```bash
git clone https://github.com/gillesturpin/ai-watch.git
cd ai-watch
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
python -m src.cli run
```

## Sources

1. **HuggingFace Daily Papers**: `GET https://huggingface.co/api/daily_papers` -> sort by upvotes -> top 3
2. **GitHub Trending**: scraping `https://github.com/trending?since=daily` (all languages) -> AI filter (LLM) -> sort by stars/day -> top 3
3. **Simon Willison RSS**: `https://simonwillison.net/atom/everything/` -> top 3 recent posts

## LLM

Single model: Claude Sonnet via Anthropic API. Two calls:
1. GitHub filter (JSON in -> JSON out, true/false per repo)
2. Enrichment + briefing (9 items -> optional tools -> markdown)

Prompts are in `/prompts/`.

## Agent Tools

The enrichment agent has 3 tools:
- `fetch_url(url)` — read a web page (httpx)
- `search_hf_models(query)` — search a model on HuggingFace Hub (API)
- `get_github_repo(owner, repo)` — read README, stars, activity (GitHub API)

The agent decides which tools to call based on each item's content.

## Briefings

Daily briefings are in [`briefings/`](./briefings/). Each briefing has a log file showing the agent's tool-use decisions.

## Project Structure

```
src/
  agent/
    graph.py        LangGraph StateGraph
    nodes.py        Node functions
    state.py        TypedDict state
    tools.py        Agent tools (fetch_url, search_hf, get_github)
  sources/
    huggingface.py  Fetch HF Daily Papers API
    github.py       Scraping GitHub Trending
    simon.py        RSS Simon Willison
  models/
    schemas.py      Pydantic models (Item, Briefing)
  utils/
    logger.py       Structured logging of agent decisions
  config.py         Settings (env vars + yaml)
  cli.py            CLI entry point
prompts/
  prompt-briefing.md       Enrichment + briefing prompt
  prompt-filter-github.md  GitHub AI filter prompt
briefings/                 Output: markdowns + logs (git tracked)
tests/
```

## Stack

- Python 3.12
- LangGraph (orchestration)
- langchain-anthropic (LLM)
- httpx (HTTP)
- beautifulsoup4 (scraping GitHub Trending)
- feedparser (RSS Simon Willison)
- ruff (lint + format)
- mypy (types)
- pytest (tests, 86% coverage)

## Dev

```bash
ruff check src/ tests/
mypy src/
pytest tests/ -v --cov=src
```

## License

MIT
