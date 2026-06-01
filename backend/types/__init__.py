# Type definitions for the ai-feedback-generator backend
from .code_context import (
    CodePosition,
    CodeRange,
    DiagnosticInfo,
    CodeContext,
)
from .feedback import (
    FeedbackItem,
    FeedbackMetadata,
    FeedbackResponse,
    FeedbackInteraction,
    FeedbackType,
    FeedbackPriority,
)
from .config import (
    FeedbackLayerConfig,
    ControllerConfig,
    SystemConfig,
    OperationMode,
)
from .messages import (
    MessageType,
    SystemStatus,
    WebSocketMessage,
    ContextRequest,
    ContextUpdate,
    FeedbackMessage,
    SystemStatusMessage,
)
from .domain_events import (
    DomainEventType,
    DomainEvent,
)

__all__ = [
    # Code context types
    "CodePosition",
    "CodeRange",
    "DiagnosticInfo",
    "CodeContext",
    # Feedback types
    "FeedbackItem",
    "FeedbackMetadata",
    "FeedbackResponse",
    "FeedbackInteraction",
    "FeedbackType",
    "FeedbackPriority",
    # Config types
    "FeedbackLayerConfig",
    "ControllerConfig",
    "SystemConfig",
    "OperationMode",
    # Message types
    "MessageType",
    "SystemStatus",
    "WebSocketMessage",
    "ContextRequest",
    "ContextUpdate",
    "FeedbackMessage",
    "SystemStatusMessage",
    # Domain event types
    "DomainEventType",
    "DomainEvent",
]
