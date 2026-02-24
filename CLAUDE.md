# AI Watch — Agent de veille IA

## Ce que c'est

Agent autonome qui tourne chaque matin (GitHub Actions cron), récupère les signaux IA importants de 3 sources, les enrichit via tool use LLM, et produit un briefing markdown quotidien.

## Architecture

```
[Fetch 3 sources en parallèle]
    → [Filtre GitHub: est-ce IA ? (LLM)]
    → [Top 3 par source]
    → [Agent enrichissement + briefing (LLM + tools)]
    → [Push briefing markdown + logs]
```

Étapes déterministes (script) : fetch, filtre, tri, top 3.
Étape agentique (LLM + tools) : enrichissement et rédaction du briefing.

## Sources

1. **HuggingFace Daily Papers** : `GET https://huggingface.co/api/daily_papers` → tri par upvotes → top 3
2. **GitHub Trending** : scraping `https://github.com/trending?since=daily` (tous langages) → filtre IA (LLM) → tri par stars/jour → top 3
3. **Simon Willison RSS** : `https://simonwillison.net/atom/everything/` → top 3 posts récents

## LLM

Un seul modèle : Claude Sonnet via l'API Anthropic. Deux appels :
1. Filtre GitHub (JSON in → JSON out, true/false par repo)
2. Enrichissement + briefing (9 items → tools optionnels → markdown)

Les prompts sont dans `/prompts/`.

## Tools de l'agent

L'agent d'enrichissement a 3 tools :
- `fetch_url(url)` — lire une page web (httpx)
- `search_hf_models(query)` — chercher un modèle sur HuggingFace Hub (API)
- `get_github_repo(owner, repo)` — lire README, stars, activité (API GitHub)

L'agent décide quels tools appeler selon le contenu de chaque item.

## Output

- Briefing : `briefings/briefing-YYYY-MM-DD.md`
- Logs : `briefings/logs-YYYY-MM-DD.json`
- Le briefing suit le format défini dans `prompts/prompt-briefing.md`

## Stack

- Python 3.12
- LangGraph (orchestration)
- langchain-anthropic (LLM)
- httpx (HTTP)
- beautifulsoup4 (scraping GitHub Trending)
- feedparser (RSS Simon Willison)
- ruff (lint + format)
- mypy (types)
- pytest (tests)

## Commandes

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
pytest tests/ -v --tb=short --cov=src
python -m src.cli run          # Lancer le pipeline
```

## Structure

```
src/
├── agent/
│   ├── graph.py        # LangGraph StateGraph
│   ├── nodes.py        # Fonctions des nœuds
│   ├── state.py        # TypedDict du state
│   └── tools.py        # Tools pour l'agent (fetch_url, search_hf, get_github)
├── sources/
│   ├── huggingface.py  # Fetch HF Daily Papers API
│   ├── github.py       # Scraping GitHub Trending
│   └── simon.py        # RSS Simon Willison
├── models/
│   └── schemas.py      # Pydantic models (Item, Briefing)
├── utils/
│   └── logger.py       # Logging structuré des décisions agent
├── config.py           # Settings (env vars + yaml)
└── cli.py              # Point d'entrée CLI
prompts/
├── prompt-briefing.md       # Prompt enrichissement + briefing
└── prompt-filter-github.md  # Prompt filtre IA GitHub
briefings/                   # Output : markdowns + logs (git tracked)
tests/
```

## Règles

- Chaque source retourne une liste de `Item` (schema Pydantic)
- Le filtre GitHub est un appel LLM séparé, avant l'agent principal
- L'agent reçoit exactement 9 items (3 par source), sauf si une source est indisponible
- Si une source échoue : le briefing est produit avec les sources restantes + note "⚠️ Source indisponible"
- Les logs tracent chaque décision de tool use de l'agent
- On ne commit jamais de clé API — tout est en env vars / GitHub Secrets
- Ruff et mypy doivent passer avant chaque commit
