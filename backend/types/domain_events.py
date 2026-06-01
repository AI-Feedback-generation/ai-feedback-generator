"""
Domain-level event types for the RuntimeController.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class DomainEventType(Enum):
    """Types of domain events emitted by the RuntimeController."""

    # Feedback events
    FEEDBACK_READY = "feedback_ready"

    # System status events
    SYSTEM_STATUS_UPDATED = "system_status_updated"

    # Code context events
    CODE_CONTEXT_NEEDED = "code_context_needed"


@dataclass
class DomainEvent:
    """A domain-level event emitted by the RuntimeController."""
    event_type: DomainEventType
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    payload: Any = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata,
        }
