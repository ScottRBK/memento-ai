"""
Domain exceptions for the application
"""

class NotFoundError(Exception):
    """Raised when a requested resource is not found"""
    pass

class ConflictError(Exception):
    """Raised when there's a resource conflict (e.g., duplicate key)"""
    pass
