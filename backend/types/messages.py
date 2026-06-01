"""
Type definitions for WebSocket and API messages.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from .code_context import CodeContext
from .feedback import FeedbackItem, FeedbackInteraction


class MessageType(Enum):
    """Types of WebSocket messages."""
    # From VS Code to Backend
    CONTEXT_UPDATE = "context_update"
    CONTEXT_REQUEST = "context_request"

    # From Backend to VS Code
    FEEDBACK_DELIVERY = "feedback_delivery"
    STATUS_UPDATE = "status_update"
    ERROR = "error"

    # Bidirectional
    PING = "ping"
    PONG = "pong"
    CONFIG_UPDATE = "config_update"


class SystemStatus(Enum):
    """System status states."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class WebSocketMessage:
    """Base WebSocket message structure."""
    type: MessageType
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: Optional[str] = None
    target_client_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "message_id": self.message_id,
            "target_client_id": self.target_client_id
        }


@dataclass
class ContextRequest:
    """Request for code context from backend to VS Code."""
    request_id: str
    timestamp: float

    include_file_content: bool = True
    include_diagnostics: bool = True
    include_visible_range: bool = True
    active_file_only: bool = True


@dataclass
class ContextUpdate:
    """Code context update from VS Code to backend."""
    request_id: Optional[str] = None
    context: CodeContext = field(default_factory=CodeContext)


@dataclass
class FeedbackMessage:
    """Feedback delivery message from backend to VS Code."""
    items: List[FeedbackItem] = field(default_factory=list)
    request_id: Optional[str] = None
    triggered_by: str = "auto"  # "auto", "manual"


@dataclass
class SystemStatusMessage:
    """System status update message."""
    status: str
    timestamp: float

    # Statistics
    feedback_generated: int = 0

    # LLM model in use
    llm_model: Optional[str] = None

    # Cooldown information
    feedback_cooldown_left_s: int = 0

    # Error information
    error_message: Optional[str] = None
