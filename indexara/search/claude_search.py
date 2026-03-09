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

Respond ONLY with valid JSON (no markdown, no explanation) in this exact format:
{"fts_query": null, "filters": {}, "limit": 50, "reasoning": "explanation"}

CRITICAL RULES:
1. fts_query = any NAME (artist, album, person, topic, keyword). NEVER omit a name. NEVER put a name only in filters.
2. filters = only structured constraints: type_group, type_subgroup, device_name
3. Words like "files", "music", "songs", "albums", "all", "my", "find", "show" are STOP WORDS — never put them in fts_query
4. Format words like "flac", "mp3", "pdf", "video" → put in filters.type_subgroup or filters.type_group, NOT in fts_query
5. If the query is ONLY about a type/format with no name, fts_query must be null
6. limit: between 10 and 200, default 50

EXAMPLES (follow these exactly):
- "radiohead flac albums" → {"fts_query":"radiohead","filters":{"type_group":"audio","type_subgroup":"flac"},"limit":50,"reasoning":"artist name in fts, format in filter"}
- "Portishead flac files" → {"fts_query":"Portishead","filters":{"type_group":"audio","type_subgroup":"flac"},"limit":50,"reasoning":"artist name in fts, format in filter"}
- "documents about taxes" → {"fts_query":"taxes","filters":{"type_group":"document"},"limit":50,"reasoning":"topic in fts, type in filter"}
- "all music files" → {"fts_query":null,"filters":{"type_group":"audio"},"limit":200,"reasoning":"no name, just type filter"}
- "all my videos" → {"fts_query":null,"filters":{"type_group":"video"},"limit":200,"reasoning":"no name, just type filter"}
- "FLAC files" → {"fts_query":null,"filters":{"type_group":"audio","type_subgroup":"flac"},"limit":200,"reasoning":"format filter only"}
- "python files" → {"fts_query":null,"filters":{"type_group":"code","type_subgroup":"python"},"limit":50,"reasoning":"format filter only"}
- "albums by Portishead" → {"fts_query":"Portishead","filters":{"type_group":"audio"},"limit":50,"reasoning":"artist name in fts"}
- "Pink Floyd mp3" → {"fts_query":"Pink Floyd","filters":{"type_group":"audio","type_subgroup":"mp3"},"limit":50,"reasoning":"artist in fts, format in filter"}
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
        interp = QueryInterpretation(
            fts_query=data.get("fts_query"),
            filters=data.get("filters", {}),
            limit=min(max(data.get("limit", 50), 1), 200),
            reasoning=data.get("reasoning"),
        )
        # Safety net: if the AI dropped a name from fts_query, recover it
        interp = _recover_fts_query(query, interp)
        return interp
    except Exception as e:
        logger.warning("AI query interpretation failed: %s", e)
        # Fallback: treat entire query as an FTS string with no filters
        return QueryInterpretation(fts_query=query, filters={}, limit=50)


# Words that describe file types/categories — should never be the fts_query on their own
_STOP_WORDS = {
    'file', 'files', 'all', 'my', 'the', 'a', 'an', 'by', 'in', 'from', 'for',
    'find', 'show', 'get', 'list', 'search', 'give', 'me',
    'music', 'audio', 'songs', 'song', 'track', 'tracks', 'album', 'albums', 'artist', 'band',
    'video', 'videos', 'movie', 'movies', 'film', 'films',
    'image', 'images', 'photo', 'photos', 'picture', 'pictures',
    'document', 'documents', 'doc', 'docs',
    'large', 'small', 'big', 'recent', 'new', 'old', 'latest',
    'flac', 'mp3', 'wav', 'ogg', 'aac', 'm4a', 'alac', 'opus',
    'mkv', 'mp4', 'avi', 'mov', 'wmv', 'webm',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'tiff',
    'pdf', 'docx', 'doc', 'xlsx', 'txt', 'epub',
    'zip', 'tar', 'rar', '7z',
}


def _recover_fts_query(original_query: str, interp: QueryInterpretation) -> QueryInterpretation:
    """If fts_query is missing, try to recover name/keyword terms from the original query."""
    if interp.fts_query:
        return interp  # AI already set it — trust it
    words = [w for w in original_query.lower().split() if w not in _STOP_WORDS]
    if not words:
        return interp  # Truly a type-only query — correct to have no fts_query
    recovered = ' '.join(words)
    logger.debug("Recovered fts_query %r from %r", recovered, original_query)
    return QueryInterpretation(
        fts_query=recovered,
        filters=interp.filters,
        limit=interp.limit,
        reasoning=interp.reasoning,
    )


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
