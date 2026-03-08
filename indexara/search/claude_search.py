"""Claude-powered query interpretation."""
from __future__ import annotations
import json
import logging
from typing import Any

from ..db.models import QueryInterpretation, SearchResult

logger = logging.getLogger(__name__)

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


def interpret_query(
    query: str,
    anthropic_client,
    model: str = "claude-haiku-4-5-20251001",
) -> QueryInterpretation:
    """Convert natural language query to structured search params."""
    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": query}],
        )
        text = response.content[0].text.strip()
        # Strip potential markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        data = json.loads(text)
        return QueryInterpretation(
            fts_query=data.get("fts_query"),
            filters=data.get("filters", {}),
            limit=min(max(data.get("limit", 50), 1), 200),
            reasoning=data.get("reasoning"),
        )
    except Exception as e:
        logger.warning("Claude query interpretation failed: %s", e)
        # Fallback: treat entire query as FTS string
        return QueryInterpretation(fts_query=query, filters={}, limit=50)


def synthesize_answer(
    question: str,
    results: list[SearchResult],
    content_snippets: list[tuple[str, str]],
    anthropic_client,
    model: str = "claude-haiku-4-5-20251001",
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
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=1024,
            system=ASK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error("Claude answer synthesis failed: %s", e)
        filenames = [r.filename for r in results[:5]]
        return f"Found {len(results)} relevant files: {', '.join(filenames)}"
