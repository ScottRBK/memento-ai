"""
Input coercion utilities for MCP tools

Handles flexible LLM input by coercing common variations into expected types.
This improves UX by accepting reasonable variations without cryptic validation errors.
"""

import json
from typing import List, Optional, Union


def coerce_to_int_list(
    value: Optional[Union[int, str, List[int]]],
    param_name: str = "parameter"
) -> Optional[List[int]]:
    """
    Coerce various input formats to List[int]

    Accepts:
    - None → None
    - [3, 7] → [3, 7]
    - 3 → [3]
    - "3" → [3]
    - "[3, 7]" → [3, 7]
    - "3,7" → [3, 7]

    Args:
        value: Input value in various formats
        param_name: Parameter name for error messages

    Returns:
        List of integers or None

    Raises:
        ValueError: If value cannot be coerced to List[int]
    """
    if value is None:
        return None

    # Already a list
    if isinstance(value, list):
        try:
            return [int(item) for item in value]
        except (ValueError, TypeError) as e:
            raise ValueError(f"{param_name}: Invalid list of integers: {value}") from e

    # Single integer
    if isinstance(value, int):
        return [value]

    # String input - try multiple formats
    if isinstance(value, str):
        value = value.strip()

        # Empty string
        if not value:
            return None

        # JSON array string like "[3, 7]"
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(item) for item in parsed]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Comma-separated like "3,7"
        if "," in value:
            try:
                return [int(item.strip()) for item in value.split(",") if item.strip()]
            except (ValueError, TypeError) as e:
                raise ValueError(f"{param_name}: Invalid comma-separated integers: {value}") from e

        # Single number as string like "3"
        try:
            return [int(value)]
        except (ValueError, TypeError) as e:
            raise ValueError(f"{param_name}: Invalid integer string: {value}") from e

    raise ValueError(f"{param_name}: Cannot coerce {type(value).__name__} to List[int]: {value}")


def coerce_to_str_list(
    value: Optional[Union[str, List[str]]],
    required: bool = False,
    param_name: str = "parameter"
) -> Optional[List[str]]:
    """
    Coerce various input formats to List[str]

    Accepts:
    - None → None (if not required) or raises ValueError (if required)
    - ['tag1', 'tag2'] → ['tag1', 'tag2']
    - 'tag1' → ['tag1']
    - "tag1,tag2" → ['tag1', 'tag2']
    - "['tag1', 'tag2']" → ['tag1', 'tag2']

    Args:
        value: Input value in various formats
        required: If True, reject None and empty values
        param_name: Parameter name for error messages

    Returns:
        List of strings or None

    Raises:
        ValueError: If value cannot be coerced to List[str] or if required and empty
    """
    if value is None:
        if required:
            raise ValueError(f"{param_name} is required")
        return None

    # Already a list
    if isinstance(value, list):
        # Filter out empty strings
        result = [str(item).strip() for item in value if str(item).strip()]
        if required and not result:
            raise ValueError(f"{param_name} cannot be empty")
        return result if result or not required else None

    # String input
    if isinstance(value, str):
        value = value.strip()

        # Empty string
        if not value:
            if required:
                raise ValueError(f"{param_name} cannot be empty")
            return None

        # JSON array string like "['tag1', 'tag2']"
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    result = [str(item).strip() for item in parsed if str(item).strip()]
                    if required and not result:
                        raise ValueError(f"{param_name} cannot be empty")
                    return result if result or not required else None
            except json.JSONDecodeError:
                pass

        # Comma-separated like "tag1,tag2"
        if "," in value:
            result = [item.strip() for item in value.split(",") if item.strip()]
            if required and not result:
                raise ValueError(f"{param_name} cannot be empty")
            return result if result or not required else None

        # Single tag
        return [value]

    raise ValueError(f"Cannot coerce {type(value).__name__} to List[str]: {value}")