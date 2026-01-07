"""
Event-driven architecture for activity tracking.

This module provides an in-process pub/sub event bus with pattern matching
for tracking entity lifecycle events across the Forgetful system.
"""

from app.events.event_bus import EventBus

__all__ = ["EventBus"]
