from pydantic import BaseModel


def get_changed_fields(input_model: BaseModel, existing_model: BaseModel) -> dict[str, tuple]:
    """
    Compares two pydantic models and returns a list of fields the old and new values of the fields that are different.

    Args:
        input_model: BaseModel of the new incoming model
        existing_model: BaseModel of the existing data that is already in the system
        
    Returns:
        dict[str, tuple]
    """
    
    input_data = input_model.model_dump(exclude_unset=True)
    existing_data = existing_model.model_dump()
    
    changes = {}

    for field_name, new_value in input_data.items():
        if field_name in existing_data:
            old_value = existing_data[field_name]
            if old_value != new_value:
                changes[field_name] = (old_value, new_value)
    
    return changes

def filter_none_values(**kwargs):
    """
    Filters out None values from keyword arguments for PATCH operations.

    This helper enables proper PATCH semantics by ensuring only explicitly
    set (non-None) values are included in update operations, preventing
    accidental clearing of existing data.

    Args:
        **kwargs: Arbitrary keyword arguments to filter

    Returns:
        dict: Dictionary containing only key-value pairs where value is not None

    Examples:
        >>> filter_none_values(title="New", content=None, importance=8)
        {'title': 'New', 'importance': 8}

        >>> filter_none_values(a=0, b="", c=None, d=False)
        {'a': 0, 'b': '', 'd': False}

    Note:
        - Empty strings, 0, False, and empty lists are preserved (only None is filtered)
        - Commonly used when building Pydantic model updates to respect exclude_unset=True
    """
    return {k: v for k, v in kwargs.items() if v is not None}