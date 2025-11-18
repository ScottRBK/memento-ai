"""Helper methods for the repository layer"""

from app.models.memory_models import MemoryCreate, Memory

import logging
logger = logging.getLogger(__name__)


def build_embedding_text(memory_data: MemoryCreate) -> str:
    """
    Build combined text for embedding generation

    Combines title, content, context, keywords and tags into a single
    text string optimized for semantic search.

    Args:
        memory_data: Memory creation

    Returns:
        Combined text string for embedding
    """
    parts = []

    if memory_data.title:
        parts.append(memory_data.title)

    if memory_data.content:
        parts.append(memory_data.content)

    if memory_data.context:
        parts.append(memory_data.context)

    if memory_data.keywords:
        parts.append(" ".join(memory_data.keywords))

    if memory_data.tags:
        parts.append(" ".join(memory_data.tags))

    combined = " ".join(parts)
    logger.debug(f"Built embedding text: {len(combined)} characters")

    return combined


def build_memory_text(memory: Memory) -> str:
    memory_parts = []

    memory_parts.append(f"Title: {memory.title or ''}")
    memory_parts.append(f"Content: {memory.content or ''}")

    if memory.context:
        memory_parts.append(f"Context: {memory.context}")

    if memory.keywords:
        keywords = ", ".join(memory.keywords)
        memory_parts.append(f"Keywords: {keywords}")

    if memory.tags:
        tags = ", ".join(memory.tags)
        memory_parts.append(f"Tags: {tags}")

    memory_text = "\n".join(memory_parts)

    return memory_text

def build_contextual_query(query: str, context: str) -> str:
    return f"query: {query}, context: {context}"

