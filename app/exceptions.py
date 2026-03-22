"""Domain exceptions for the application
"""

class NotFoundError(Exception):
    """Raised when a requested resource is not found"""

class ConflictError(Exception):
    """Raised when there's a resource conflict (e.g., duplicate key)"""


class InvalidStateTransitionError(Exception):
    """Raised when a state machine transition is not allowed"""


class DependencyNotMetError(Exception):
    """Raised when task dependencies are not satisfied for a transition"""


class CyclicDependencyError(Exception):
    """Raised when adding a dependency would create a cycle"""
