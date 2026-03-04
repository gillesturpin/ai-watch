You receive a list of GitHub trending repos. For each repo, answer `true` or `false`: is this repo related to AI, machine learning, or LLMs?

## Criteria

AI-related (`true`):
- Models, frameworks, ML/DL tools
- AI agents, assistants, chatbots
- Prompts, prompt engineering, system prompts
- RAG, embeddings, vector databases
- Fine-tuning, training, model evaluation
- Wrappers/UIs for AI tools (e.g., interface for Claude Code)
- ML datasets

Not AI-related (`false`):
- Networking tools, VPN, proxy
- Games, streaming, media
- General infrastructure (unless specifically for ML)
- Non-AI awesome lists
- General-purpose DevOps/CI/CD

## Input format

```json
[
  {"repo": "owner/name", "description": "...", "language": "..."},
  ...
]
```

## Output format

```json
[
  {"repo": "owner/name", "is_ai": true},
  ...
]
```

Reply with the JSON only, nothing else.
