"""
Domain exceptions for the application
"""

class NotFoundError(Exception):
    """Raised when a requested resource is not found"""
    pass

class ConflictError(Exception):
    """Raised when there's a resource conflict (e.g., duplicate key)"""
    pass


class InvalidStateTransitionError(Exception):
    """Raised when a state machine transition is not allowed"""
    pass


class DependencyNotMetError(Exception):
    """Raised when task dependencies are not satisfied for a transition"""
    pass


class CyclicDependencyError(Exception):
    """Raised when adding a dependency would create a cycle"""
    pass
