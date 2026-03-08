"""AI-powered query interpretation — supports Anthropic and any OpenAI-compatible endpoint.

OpenAI-compatible providers (Ollama, LM Studio, llama.cpp) are supported by setting:
    ai_provider: openai-compatible
    ai_base_url: http://localhost:11434/v1   # Ollama default
    ai_model: llama3.2                        # or mistral, qwen2.5, etc.

No extra dependencies needed — uses httpx (already required) for the OpenAI-compatible path.
"""
from __future__ import annotations
import json
import logging
from typing import Any

import httpx

from ..db.models import QueryInterpretation, SearchResult

logger = logging.getLogger(__name__)

# Default models per provider
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_LOCAL_MODEL = "llama3.2"

SYSTEM_PROMPT = """You are a query interpreter for Indexara, a personal file catalogue.
Your job is to convert natural language queries into structured search parameters.

The catalogue contains files with these fields:
- filename: the file's name
- path: full file path
- type_group: "audio", "document", "image", "video", "archive", "code", "data", "other"
- type_subgroup: specific format like "flac", "mp3", "pdf", "docx", "jpeg", "mkv", "zip", "python"
- device_name: which machine the file is on
- extension: file extension without dot
- audio metadata: artist, album, title (for audio files)
- document_text: extracted text content (for documents)

Respond ONLY with valid JSON (no markdown, no explanation) in this format:
{
  "fts_query": "search terms for full-text search, or null if not needed",
  "filters": {
    "type_group": "audio",
    "type_subgroup": "flac"
  },
  "limit": 50,
  "reasoning": "brief explanation"
}

Rules:
- Use fts_query for text/name searches, artist/album names, document content searches
- Use filters for structured constraints (file type, format, device)
- filters keys must be one of: type_group, type_subgroup, device_name, extension
- For audio searches, set type_group="audio"
- For format-specific searches (e.g. "FLAC files"), set type_subgroup
- limit should be between 10 and 200, default 50
- If the query is purely structural (e.g. "all PDF files"), fts_query can be null
- Both fts_query and filters can be set simultaneously for best results

Examples:
- "radiohead flac albums" → fts_query="radiohead", filters={"type_group":"audio","type_subgroup":"flac"}
- "documents about taxes" → fts_query="taxes", filters={"type_group":"document"}
- "all my videos" → fts_query=null, filters={"type_group":"video"}
- "python files" → fts_query=null, filters={"type_group":"code","type_subgroup":"python"}
"""

ASK_SYSTEM_PROMPT = """You are a helpful assistant answering questions about a user's files.
You will be given file records and extracted text snippets from those files.
Answer the user's question based ONLY on the provided file content.
If the files don't contain enough information to answer, say so clearly.
Be concise and cite specific files when relevant.
"""


def _call_llm(
    system: str,
    user: str,
    config,
    max_tokens: int = 512,
) -> str:
    """Call either Anthropic or an OpenAI-compatible local endpoint."""
    if config.ai_provider == "openai-compatible":
        return _call_openai_compatible(system, user, config, max_tokens)
    else:
        return _call_anthropic(system, user, config, max_tokens)


def _call_anthropic(system: str, user: str, config, max_tokens: int) -> str:
    import anthropic
    model = config.ai_model or DEFAULT_ANTHROPIC_MODEL
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_openai_compatible(system: str, user: str, config, max_tokens: int) -> str:
    """Call any OpenAI-compatible chat completions endpoint (Ollama, LM Studio, etc.)."""
    base_url = (config.ai_base_url or "http://localhost:11434/v1").rstrip("/")
    model = config.ai_model or DEFAULT_LOCAL_MODEL

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,  # low temperature for structured JSON output
    }

    headers = {"Content-Type": "application/json"}
    # Some providers (LM Studio, hosted OpenAI-compatible) need an API key
    if config.anthropic_api_key:
        headers["Authorization"] = f"Bearer {config.anthropic_api_key}"

    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def interpret_query(query: str, config) -> QueryInterpretation:
    """Convert natural language query to structured search params."""
    try:
        text = _call_llm(SYSTEM_PROMPT, query, config, max_tokens=512)
        data = _parse_json_response(text)
        return QueryInterpretation(
            fts_query=data.get("fts_query"),
            filters=data.get("filters", {}),
            limit=min(max(data.get("limit", 50), 1), 200),
            reasoning=data.get("reasoning"),
        )
    except Exception as e:
        logger.warning("AI query interpretation failed: %s", e)
        # Fallback: treat entire query as an FTS string with no filters
        return QueryInterpretation(fts_query=query, filters={}, limit=50)


def synthesize_answer(
    question: str,
    results: list[SearchResult],
    content_snippets: list[tuple[str, str]],
    config,
) -> str:
    """Generate an answer using retrieved file content as context."""
    if not results:
        return "No relevant files found in your catalogue to answer this question."

    context_parts = []
    for result, (filename, snippet) in zip(results[:10], content_snippets[:10]):
        context_parts.append(
            f"File: {filename} ({result.path})\n"
            f"Content excerpt: {snippet[:500]}"
        )

    context = "\n\n---\n\n".join(context_parts)
    user_message = f"Question: {question}\n\nRelevant files:\n\n{context}"

    try:
        return _call_llm(ASK_SYSTEM_PROMPT, user_message, config, max_tokens=1024)
    except Exception as e:
        logger.error("AI answer synthesis failed: %s", e)
        filenames = [r.filename for r in results[:5]]
        return f"Found {len(results)} relevant files: {', '.join(filenames)}"
