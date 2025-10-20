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