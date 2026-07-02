"""
Runtime Controller

Receives code context from VS Code, generates LLM feedback on context changes
(subject to a cooldown), and delivers feedback back via domain events.
"""
import contextlib
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
import asyncio

from backend.feedback_layer import FeedbackLayer
from backend.logger_service import get_logger
from backend.types.code_context import CodeContext
from backend.types.config import SystemConfig
from backend.types.feedback import FeedbackInteraction, FeedbackResponse
from backend.types.messages import SystemStatus, SystemStatusMessage
from backend.types.domain_events import DomainEvent, DomainEventType


class RuntimeController:
    """Central orchestrator: receives code context → generates LLM feedback → delivers via events."""

    def __init__(self, config: Optional[SystemConfig] = None):
        self._config = config or SystemConfig()
        self._logger = get_logger()

        self._feedback_layer = FeedbackLayer(
            self._config.feedback_layer,
            logger=self._logger
        )

        # State
        self._status: SystemStatus = SystemStatus.INITIALIZING
        self._last_feedback_time: float = 0.0
        self._current_code_context: Optional[CodeContext] = None

        # Feedback pipeline state
        self._context_version: int = 0
        self._pending_feedback: Optional[FeedbackResponse] = None
        self._pending_feedback_version: int = 0
        self._last_delivered_version: int = 0
        self._feedback_generation_task: Optional[asyncio.Task] = None

        self._stats: Dict[str, Any] = {
            "feedback_generated": 0,
            "session_start": None,
        }

        self._event_handlers: List[Callable[[DomainEvent], None]] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._main_loop_task: Optional[asyncio.Task] = None

        self._logger.system(
            "runtime_controller_initialized",
            {},
            level="DEBUG",
        )

    async def initialize(self) -> bool:
        self._status = SystemStatus.INITIALIZING
        self._stats["session_start"] = asyncio.get_event_loop().time()
        self._loop = asyncio.get_event_loop()

        llm_ready = self._feedback_layer.initialize_llm()
        if not llm_ready:
            self._logger.system("llm_not_configured", {"fallback": "heuristics"}, level="WARNING")

        self._main_loop_task = asyncio.create_task(self._run_main_loop())
        self._status = SystemStatus.RUNNING
        self._logger.system("runtime_controller_ready", self.get_system_status(), level="INFO")
        return True

    async def shutdown(self) -> None:
        self._logger.system("runtime_controller_shutdown", {"final_stats": self._stats}, level="INFO")
        self._status = SystemStatus.STOPPED

        if self._feedback_generation_task and not self._feedback_generation_task.done():
            self._feedback_generation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._feedback_generation_task

        if self._main_loop_task:
            self._main_loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._main_loop_task

        self._status = SystemStatus.DISCONNECTED

    def get_system_status(self) -> SystemStatusMessage:
        return SystemStatusMessage(
            status=self._status.value,
            timestamp=datetime.now(timezone.utc).timestamp(),
            feedback_generated=self._stats["feedback_generated"],
            llm_model=self._feedback_layer.get_llm_client().get_model_name() if self._feedback_layer.get_llm_client() else None,
            feedback_cooldown_left_s=int(self.get_feedback_cooldown_remaining()),
        )

    async def handle_context_update(self, context: CodeContext) -> None:
        self._current_code_context = context
        self._context_version += 1
        current_version = self._context_version

        self._logger.system(
            "context_update_received",
            {
                "file": context.file_path,
                "line": context.cursor_position.line,
                "context_version": current_version,
            },
            level="INFO",
        )

        # Cancel any ongoing generation — new context makes it stale
        if self._feedback_generation_task is not None and not self._feedback_generation_task.done():
            self._feedback_generation_task.cancel()
            self._logger.system(
                "feedback_generation_cancelled",
                {"reason": "new_context_arrived"},
                level="DEBUG",
            )

        if self._can_start_feedback_generation():
            self._feedback_generation_task = asyncio.create_task(
                self._generate_feedback_for_version(current_version, context)
            )

    def manual_send_feedback(self) -> bool:
        """Deliver latest pending feedback immediately, bypassing cooldown."""
        self._logger.system(
            "manual_feedback_triggered",
            {
                "pending_feedback_version": self._pending_feedback_version,
                "last_delivered_version": self._last_delivered_version,
                "cooldown_remaining": self.get_feedback_cooldown_remaining(),
            },
        )
        # Only re-deliver pending feedback if it hasn't been sent already and has items
        if (
            self._pending_feedback is not None
            and self._pending_feedback.items
            and self._pending_feedback_version > self._last_delivered_version
        ):
            return self._try_deliver_feedback(force=True)

        # No undelivered pending feedback — generate fresh from current context
        if self._current_code_context is None:
            return False

        asyncio.create_task(
            self._generate_feedback_for_version(self._context_version, self._current_code_context, force_deliver=True)
        )
        return True

    async def handle_feedback_interaction(self, interaction: FeedbackInteraction) -> bool:
        interaction_type = (
            interaction.interaction_type.value
            if hasattr(interaction.interaction_type, "value")
            else str(interaction.interaction_type)
        )

        category_map = {
            "presented": "feedback_presented_to_user",
            "accepted": "feedback_accepted_by_user",
            "rejected": "feedback_rejected_by_user",
            "highlighted": "feedback_highlighted_in_code",
            "dismissed": "feedback_dismissed_by_user",
            "done": "feedback_marked_done_by_user",
        }
        category_msg = category_map.get(
            interaction_type,
            f"feedback_interaction_unknown_type: {interaction_type}"
        )

        self._logger.system(
            category_msg,
            {"feedback_id": interaction.feedback_id, "action_taken": interaction_type},
            level="INFO",
        )

        if interaction_type in ("dismissed", "done"):
            self._remove_feedback_from_pending(interaction.feedback_id)
            self._trigger_new_feedback_after_interaction()

        return True

    def _trigger_new_feedback_after_interaction(self) -> None:
        if self._current_code_context is None or self._status != SystemStatus.RUNNING:
            return

        if self._feedback_generation_task is not None and not self._feedback_generation_task.done():
            self._feedback_generation_task.cancel()

        self._feedback_generation_task = asyncio.create_task(
            self._generate_feedback_for_version(
                self._context_version, self._current_code_context, force_deliver=True
            )
        )
        self._logger.system("feedback_generation_triggered_by_interaction", {}, level="DEBUG")

    def _remove_feedback_from_pending(self, feedback_id: str) -> None:
        if self._pending_feedback is None:
            return

        original_count = len(self._pending_feedback.items)
        filtered_items = [
            item for item in self._pending_feedback.items
            if item.metadata.feedback_id != feedback_id
        ]

        if len(filtered_items) == original_count:
            return

        self._pending_feedback.items = filtered_items
        if not self._pending_feedback.items:
            self._pending_feedback = None
            self._pending_feedback_version = 0

        self._logger.system(
            "feedback_removed_from_pending_cache",
            {
                "feedback_id": feedback_id,
                "pending_items_remaining": len(filtered_items),
            },
            level="DEBUG",
        )

    def register_event_handler(self, handler: Callable[[DomainEvent], None]) -> None:
        self._event_handlers.append(handler)

    def _publish(self, event: DomainEvent) -> None:
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.system(
                    "event_handler_error",
                    {"error": str(e), "event_type": event.event_type.value},
                    level="ERROR",
                )

    # Only start generation when delivery is imminent to avoid wasted LLM calls.
    _GENERATION_LEAD_TIME_S = 10.0

    def _can_start_feedback_generation(self) -> bool:
        if self._status != SystemStatus.RUNNING:
            return False
        if self._current_code_context is None:
            return False
        if self.get_feedback_cooldown_remaining() > self._GENERATION_LEAD_TIME_S:
            return False
        return True

    def _should_deliver_feedback(self) -> bool:
        if self._status != SystemStatus.RUNNING:
            return False
        if self._pending_feedback is None:
            return False
        if self._pending_feedback_version <= self._last_delivered_version:
            return False
        if self.get_feedback_cooldown_remaining() > 0.0:
            self._logger.system(
                "feedback_delivery_cooldown",
                {"remaining": self.get_feedback_cooldown_remaining()},
                level="DEBUG",
            )
            return False
        return True

    def _try_deliver_feedback(self, force: bool = False) -> bool:
        if force:
            if self._status != SystemStatus.RUNNING:
                return False
            if self._pending_feedback is None:
                return False
            feedback = self._pending_feedback
            version = self._pending_feedback_version
        else:
            if not self._should_deliver_feedback():
                return False
            feedback = self._pending_feedback
            version = self._pending_feedback_version

        self._last_delivered_version = max(self._last_delivered_version, version)
        self._last_feedback_time = asyncio.get_event_loop().time()

        recipient_id = None
        if self._current_code_context and self._current_code_context.metadata:
            recipient_id = self._current_code_context.metadata.get("requester_id")

        event_meta = {"recipient_id": recipient_id} if recipient_id else {}
        event_meta["feedback_version"] = version
        event_meta["trigger"] = "manual" if force else "auto"

        self._publish(DomainEvent(
            event_type=DomainEventType.FEEDBACK_READY,
            payload=feedback,
            metadata=event_meta,
        ))

        self._logger.system(
            "feedback_delivered",
            {
                "trigger": event_meta["trigger"],
                "feedback_version": version,
                "item_count": len(feedback.items),
                "item_ids": [item.metadata.feedback_id for item in feedback.items],
            },
            level="INFO",
        )
        return True

    async def _generate_feedback_for_version(
        self,
        version: int,
        context: CodeContext,
        force_deliver: bool = False,
    ) -> None:
        try:
            self._logger.system(
                "feedback_generation_started",
                {"version": version},
                level="DEBUG",
            )

            feedback = await self._feedback_layer.generate_feedback_cached(context=context)

            for item in feedback.items:
                self._logger.feedback("feedback_item_generated", item)

            # Stale check: a newer context arrived during generation.
            # Skip for manual (force_deliver) triggers — the user asked for feedback
            # and should get it even if context changed during the LLM call.
            if not force_deliver and version != self._context_version:
                self._logger.system(
                    "feedback_generation_stale",
                    {
                        "generated_version": version,
                        "current_version": self._context_version,
                    },
                    level="DEBUG",
                )
                return

            if feedback is not None and feedback.items:
                self._pending_feedback = feedback
                self._pending_feedback_version = version
                self._stats["feedback_generated"] = self._stats.get("feedback_generated", 0) + 1
                self._try_deliver_feedback(force=force_deliver)
            else:
                self._logger.system(
                    "feedback_generation_empty",
                    {"version": version},
                    level="DEBUG",
                )

        except asyncio.CancelledError:
            self._logger.system(
                "feedback_generation_cancelled",
                {"version": version},
                level="DEBUG",
            )
            raise
        except Exception as e:
            self._logger.system(
                "feedback_generation_error",
                {"version": version, "error": str(e)},
                level="ERROR",
            )

    def get_feedback_cooldown_remaining(self) -> float:
        current_time = asyncio.get_event_loop().time()
        cooldown = self._config.controller.feedback_cooldown_seconds
        last_feedback_time = self._last_feedback_time
        if last_feedback_time == 0.0:
            last_feedback_time = self._stats.get("session_start", current_time)
        elapsed = current_time - last_feedback_time
        return max(0.0, cooldown - elapsed)

    def reset_feedback_cooldown(self) -> None:
        self._last_feedback_time = asyncio.get_event_loop().time()
        self._logger.system(
            "feedback_cooldown_reset",
            {"timestamp": self._last_feedback_time},
            level="DEBUG",
        )

    def set_feedback_cooldown(self, cooldown_seconds: float) -> None:
        self._last_feedback_time = asyncio.get_event_loop().time()
        self._config.controller.feedback_cooldown_seconds = cooldown_seconds
        self._logger.system(
            "feedback_cooldown_changed",
            {"new_cooldown_seconds": cooldown_seconds},
            level="INFO",
        )
        self._publish(DomainEvent(
            event_type=DomainEventType.SYSTEM_STATUS_UPDATED,
            payload=self.get_system_status(),
        ))
        if cooldown_seconds == 0 and self._current_code_context is not None:
            if self._feedback_generation_task is not None and not self._feedback_generation_task.done():
                self._feedback_generation_task.cancel()
            self._feedback_generation_task = asyncio.create_task(
                self._generate_feedback_for_version(
                    self._context_version, self._current_code_context
                )
            )

    def _maybe_trigger_feedback_on_cooldown_expiry(self) -> None:
        if not self._can_start_feedback_generation():
            return
        if self._feedback_generation_task is not None and not self._feedback_generation_task.done():
            return
        self._feedback_generation_task = asyncio.create_task(
            self._generate_feedback_for_version(self._context_version, self._current_code_context)
        )
        self._logger.system("feedback_generation_triggered_by_cooldown_expiry", {}, level="DEBUG")

    async def _run_main_loop(self) -> None:
        self._logger.system("runtime_controller_main_loop_started", {}, level="DEBUG")
        while self._status != SystemStatus.DISCONNECTED:
            await asyncio.sleep(1)
            self._broadcast_system_status()
            self._maybe_trigger_feedback_on_cooldown_expiry()
        self._logger.system("runtime_controller_main_loop_ended", {}, level="DEBUG")

    def _broadcast_system_status(self) -> None:
        self._publish(DomainEvent(
            event_type=DomainEventType.SYSTEM_STATUS_UPDATED,
            payload=self.get_system_status(),
        ))
