"""
Utility functions for formatting error messages
"""
from pydantic import ValidationError


def format_validation_error(e: ValidationError) -> str:
    """
    Format Pydantic ValidationError with full field-level details.

    Converts ValidationError into a readable string that includes:
    - The model name
    - Each field error with location, message, and error type

    Args:
        e: Pydantic ValidationError instance

    Returns:
        Formatted error string with all validation details

    Example:
        ValidationError for Model with 2 errors:
        - field 'name': Field required [type=missing]
        - field 'age': Input should be a valid integer [type=int_parsing]
    """
    errors = e.errors()
    model_name = e.title
    error_count = len(errors)

    # Format header
    result = f"ValidationError for {model_name} with {error_count} error(s):\n"

    # Format each error
    for error in errors:
        # Get location (convert tuple to dot-separated path)
        loc = error.get('loc', ())
        if loc:
            loc_str = '.'.join(str(x) for x in loc)
        else:
            loc_str = 'unknown'

        # Get message and type
        msg = error.get('msg', 'Unknown error')
        error_type = error.get('type', 'unknown')

        # Format as: - field 'location': message [type=error_type]
        result += f"  - field '{loc_str}': {msg} [type={error_type}]\n"

    return result.strip()
