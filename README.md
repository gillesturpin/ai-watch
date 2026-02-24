# 📰 AI Watch — Agent de veille IA

Agent autonome qui produit un briefing quotidien à partir de 3 sources : HuggingFace Papers, GitHub Trending, et Simon Willison.

Tourne chaque matin via GitHub Actions. Filtre, enrichit, résume. Pas un notebook one-shot — un système qui produit un résultat neuf chaque jour.

## Quick Start

```bash
git clone https://github.com/youruser/ai-watch.git
cd ai-watch
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Ajouter ANTHROPIC_API_KEY dans .env
python -m src.cli run
```

## Comment ça marche

```
HuggingFace Papers API ──┐
GitHub Trending (scrape) ─┤── Top 3 par source ── Agent LLM + Tools ── Briefing Markdown
Simon Willison RSS ───────┘
```

L'agent décide pour chaque item s'il a besoin de plus de contexte :
- Papier mentionne un modèle → cherche sur HF Hub (downloads, licence)
- Description GitHub vague → lit le README
- Post Simon avec juste un titre → fetch le contenu complet

## Briefings

Les briefings quotidiens sont dans [`briefings/`](./briefings/). Chaque briefing a un fichier de logs qui montre les décisions de l'agent.

## Dev

```bash
ruff check src/ tests/
mypy src/
pytest tests/ -v --cov=src
```

## License

MIT
