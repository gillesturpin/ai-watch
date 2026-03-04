"""LangGraph node functions.

Pipeline:
    fetch_sources (parallel) → filter_github → combine_items → enrich_and_brief
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from src.agent.state import AgentState
from src.agent.tools import fetch_url, get_github_repo, search_hf_models
from src.config import load_config
from src.models.schemas import EnrichmentLog, Item, SourceType
from src.sources.github import fetch_github_trending
from src.sources.huggingface import fetch_huggingface_papers
from src.sources.simon import fetch_simon_willison

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _get_llm() -> ChatAnthropic:
    config = load_config()
    return ChatAnthropic(  # type: ignore[call-arg]
        model=config["llm_model"],
        api_key=config["anthropic_api_key"],
        max_tokens=4096,
    )


async def _llm_invoke_with_retry(llm: Runnable[Any, Any], messages: list, max_retries: int = 1):
    """Invoke LLM with retry on failure (SPEC: retry 1 fois)."""
    for attempt in range(max_retries + 1):
        try:
            return await llm.ainvoke(messages)
        except Exception:
            if attempt == max_retries:
                raise
            logger.warning(
                "LLM call failed (attempt %d/%d), retrying...", attempt + 1, max_retries + 1
            )


async def fetch_sources(state: AgentState) -> AgentState:
    """Fetch all 3 sources in parallel. Handles individual source failures."""
    sources_status: dict[str, str] = {}

    results = await asyncio.gather(
        fetch_huggingface_papers(),
        fetch_github_trending(),
        fetch_simon_willison(),
        return_exceptions=True,
    )

    # HuggingFace
    hf_items: list[Item] = []
    if isinstance(results[0], BaseException):
        logger.error("HuggingFace fetch failed: %s", results[0])
        sources_status["huggingface"] = f"error: {results[0]}"
    else:
        hf_items = results[0]
        sources_status["huggingface"] = "ok"

    # GitHub
    gh_items_raw: list[Item] = []
    if isinstance(results[1], BaseException):
        logger.error("GitHub fetch failed: %s", results[1])
        sources_status["github"] = f"error: {results[1]}"
    else:
        gh_items_raw = results[1]
        sources_status["github"] = "ok"

    # Simon
    simon_items: list[Item] = []
    if isinstance(results[2], BaseException):
        logger.error("Simon Willison fetch failed: %s", results[2])
        sources_status["simon"] = f"error: {results[2]}"
    else:
        simon_items = results[2]
        sources_status["simon"] = "ok"

    return {
        **state,
        "hf_items": hf_items,
        "gh_items_raw": gh_items_raw,
        "simon_items": simon_items,
        "sources_status": sources_status,
    }


async def filter_github(state: AgentState) -> AgentState:
    """Filter GitHub repos: call LLM to identify AI-related repos, keep top 3."""
    gh_items = state.get("gh_items_raw", [])

    if not gh_items:
        return {**state, "gh_items_filtered": []}

    # Build input JSON for the filter prompt
    repos_json = json.dumps(
        [
            {
                "repo": f"{item.repo_owner}/{item.repo_name}",
                "description": item.description,
                "language": item.language,
            }
            for item in gh_items
        ],
        ensure_ascii=False,
    )

    # Load filter prompt
    prompt_text = (PROMPTS_DIR / "prompt-filter-github.md").read_text(encoding="utf-8")

    llm = _get_llm()
    response = await _llm_invoke_with_retry(
        llm,
        [
            SystemMessage(content=prompt_text),
            HumanMessage(content=repos_json),
        ],
    )

    # Parse response JSON
    try:
        # Strip markdown code fences if present
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        filter_results = json.loads(content)
    except json.JSONDecodeError:
        logger.error("Failed to parse GitHub filter response: %s", response.content[:200])
        # Fallback: skip GitHub source entirely rather than accepting unfiltered repos
        return {**state, "gh_items_filtered": []}

    # Build set of AI repos
    ai_repos = {r["repo"] for r in filter_results if r.get("is_ai")}
    logger.info("GitHub filter: %d/%d repos marked as AI", len(ai_repos), len(gh_items))

    # Filter and sort by stars_today
    filtered = [item for item in gh_items if f"{item.repo_owner}/{item.repo_name}" in ai_repos]
    filtered.sort(key=lambda x: x.stars_today, reverse=True)

    return {**state, "gh_items_filtered": filtered[:3]}


async def combine_items(state: AgentState) -> AgentState:
    """Combine top items from all sources into items_to_enrich."""
    items = []
    items.extend(state.get("hf_items", []))
    items.extend(state.get("gh_items_filtered", []))
    items.extend(state.get("simon_items", []))

    logger.info("Combined %d items for enrichment", len(items))
    return {**state, "items_to_enrich": items}


def _match_tool_call_to_item(
    tool_name: str, tool_args: dict, item_by_url: dict[str, Item], items: list[Item]
) -> Item | None:
    """Best-effort match a tool call to the item it enriches."""
    # fetch_url: match by URL
    if tool_name == "fetch_url" and "url" in tool_args:
        url = tool_args["url"]
        if url in item_by_url:
            return item_by_url[url]
        # Partial match (URL might differ slightly)
        for item in items:
            if item.url and item.url in url:
                return item

    # get_github_repo: match by owner/repo
    if tool_name == "get_github_repo":
        owner = tool_args.get("owner", "")
        repo = tool_args.get("repo", "")
        for item in items:
            if item.repo_owner == owner and item.repo_name == repo:
                return item

    # search_hf_models: match by query against titles
    if tool_name == "search_hf_models" and "query" in tool_args:
        query = tool_args["query"].lower()
        for item in items:
            if query in item.title.lower():
                return item

    return None


def _format_items_for_prompt(items: list) -> str:
    """Format items as text block for the enrichment prompt."""
    sections = []

    for i, item in enumerate(items, 1):
        if item.source == SourceType.HUGGINGFACE:
            sections.append(
                f"[HF-{i}] {item.title}\n"
                f"  upvotes: {item.upvotes}\n"
                f"  auteurs: {item.authors}\n"
                f"  url: {item.url}\n"
                f"  abstract: {item.abstract}\n"
            )
        elif item.source == SourceType.GITHUB:
            sections.append(
                f"[GH-{i}] {item.repo_owner}/{item.repo_name}\n"
                f"  description: {item.description}\n"
                f"  stars/jour: {item.stars_today}\n"
                f"  langage: {item.language}\n"
                f"  url: {item.url}\n"
            )
        elif item.source == SourceType.SIMON:
            sections.append(
                f"[SW-{i}] {item.title}\n"
                f"  url: {item.url}\n"
                f"  tags: {', '.join(item.tags)}\n"
                f"  extrait: {item.content_snippet[:300]}\n"
            )

    return "\n".join(sections)


async def enrich_and_brief(state: AgentState) -> AgentState:
    """Agent with tools: enrich items and produce the briefing markdown."""
    items = state.get("items_to_enrich", [])

    if not items:
        return {
            **state,
            "briefing_markdown": "# AI Briefing\n\nNo items available today.\n",
            "enrichment_logs": [],
        }

    # Load briefing prompt
    prompt_text = (PROMPTS_DIR / "prompt-briefing.md").read_text(encoding="utf-8")

    # Format items
    items_text = _format_items_for_prompt(items)

    # Add unavailable sources warning
    sources_status = state.get("sources_status", {})
    warnings = []
    for source, status in sources_status.items():
        if status != "ok":
            warnings.append(f"⚠️ Source indisponible : {source}")
    warning_text = "\n".join(warnings) if warnings else ""

    # Create agent with tools
    llm = _get_llm()
    tools = [fetch_url, search_hf_models, get_github_repo]
    llm_with_tools = llm.bind_tools(tools)

    # Build messages
    messages = [
        SystemMessage(content=prompt_text),
        HumanMessage(
            content=f"Date du jour : {state.get('today', 'inconnue')}\n\n"
            f"<items>\n{items_text}\n</items>\n\n{warning_text}"
        ),
    ]

    # Build item lookup for enrichment logging
    item_by_url: dict[str, Item] = {item.url: item for item in items}

    # Agent loop: call LLM, execute tools, repeat until done
    enrichment_logs: list[EnrichmentLog] = []
    llm_calls = 0
    total_tokens = 0
    max_iterations = 10

    from langchain_core.messages import ToolMessage

    response = None
    for _iteration in range(max_iterations):
        response = await _llm_invoke_with_retry(llm_with_tools, messages)
        llm_calls += 1
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            total_tokens += response.usage_metadata.get("total_tokens", 0)
        messages.append(response)

        # Check for tool calls
        if not response.tool_calls:
            break

        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            logger.info("Tool call: %s(%s)", tool_name, tool_args)

            # Find and execute the tool
            tool_fn = {
                "fetch_url": fetch_url,
                "search_hf_models": search_hf_models,
                "get_github_repo": get_github_repo,
            }[tool_name]

            try:
                result = await tool_fn.ainvoke(tool_args)
            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e)
                result = f"Erreur: {e}"

            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

            # Resolve which item this tool call relates to
            matched_item = _match_tool_call_to_item(tool_name, tool_args, item_by_url, items)
            enrichment_logs.append(
                EnrichmentLog(
                    item_title=matched_item.title if matched_item else str(tool_args),
                    source=matched_item.source if matched_item else SourceType.HUGGINGFACE,
                    tools_called=[tool_name],
                    reason=f"{tool_name}({tool_args})",
                )
            )
    else:
        # Max iterations reached — force a final call without tools to get the briefing
        logger.warning("Agent hit max iterations (%d), forcing final response", max_iterations)
        response = await _llm_invoke_with_retry(llm, messages)

    # Extract the final text response
    briefing_markdown = response.content if response else ""
    if isinstance(briefing_markdown, list):
        # Handle case where content is a list of blocks
        briefing_markdown = "\n".join(
            block.get("text", "") for block in briefing_markdown if block.get("type") == "text"
        )

    return {
        **state,
        "briefing_markdown": briefing_markdown,
        "enrichment_logs": enrichment_logs,
        "llm_calls": llm_calls,
        "total_tokens": total_tokens,
    }
