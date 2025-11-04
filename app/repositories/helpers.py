"""Helper methods for the repository layer"""

from app.models.memory_models import MemoryCreate, MemoryUpdate

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
    parts = [
        memory_data.title,
        memory_data.content,
    ]

    if memory_data.context:
        parts.append(memory_data.context)

    if memory_data.keywords:
        parts.append(" ".join(memory_data.keywords))
        
    if memory_data.tags:
        parts.append(" ".join(memory_data.tags))

    combined = " ".join(parts)
    logger.debug(f"Built embedding text: {len(combined)} characters")

    return combined

