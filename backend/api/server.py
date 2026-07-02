"""
Combined Server

Runs WebSocket and REST API servers together. Wires the RuntimeController
to network interfaces for bidirectional communication with VS Code.
"""
import datetime
from typing import Optional, Dict, Any
import asyncio
import signal

from backend.api.serialization import json_safe
from backend.types import SystemConfig
from backend.controller import RuntimeController
from backend.api.websocket_server import WebSocketServer
from backend.api.rest_api import HttpMethod, RestAPI
from backend.logger_service import get_logger
from backend.types.code_context import CodeContext
from backend.types.messages import MessageType, WebSocketMessage
from backend.types.domain_events import DomainEvent, DomainEventType
from backend.types.feedback import FeedbackInteraction


class Server:
    """Main server combining WebSocket and REST API."""

    def __init__(self, config: Optional[SystemConfig] = None):
        self._config = config or SystemConfig()

        self._controller = RuntimeController(self._config)
        self._websocket_server = WebSocketServer(
            host=self._config.controller.websocket_host,
            port=self._config.controller.websocket_port,
        )
        self._rest_api = RestAPI(
            host=self._config.controller.api_host,
            port=self._config.controller.api_port,
        )

        self._is_running: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._logger = get_logger()

    async def start(self) -> None:
        """Start all server components."""
        self._logger.system(
            "servers_starting",
            {
                "websocket_url": f"ws://{self._config.controller.websocket_host}:{self._config.controller.websocket_port}",
                "api_url": f"http://{self._config.controller.api_host}:{self._config.controller.api_port}",
            },
        )

        self._wire_components()
        await self._websocket_server.start()
        await self._rest_api.start()
        await self._controller.initialize()

        self._is_running = True
        self._logger.system("servers_started", {})

    async def stop(self) -> None:
        """Stop all server components gracefully."""
        self._logger.system("servers_stopping", {})
        self._is_running = False

        await self._controller.shutdown()
        await self._websocket_server.stop()
        await self._rest_api.stop()

        self._logger.system("servers_stopped", {})

    def run(self) -> None:
        """Run the server (blocking)."""
        self._loop = asyncio.get_event_loop()
        self._setup_signal_handlers()

        try:
            self._loop.run_until_complete(self.start())
            self._loop.run_forever()
        except KeyboardInterrupt:
            self._logger.system("keyboard_interrupt", {})
        finally:
            self._loop.run_until_complete(self.stop())
            self._loop.close()

    async def run_async(self) -> None:
        """Run the server asynchronously."""
        await self.start()

    def is_running(self) -> bool:
        return self._is_running

    def get_controller(self) -> RuntimeController:
        return self._controller

    def get_websocket_server(self) -> WebSocketServer:
        return self._websocket_server

    def get_rest_api(self) -> RestAPI:
        return self._rest_api

    # --- Internal Methods ---

    def _setup_signal_handlers(self) -> None:
        if self._loop is None:
            return

        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._shutdown_handler(s))
            )

    def _wire_components(self) -> None:
        # Controller → WebSocket (outbound) via domain events
        def handle_domain_event(event: DomainEvent) -> None:
            event_to_message_type = {
                DomainEventType.FEEDBACK_READY: MessageType.FEEDBACK_DELIVERY,
                DomainEventType.SYSTEM_STATUS_UPDATED: MessageType.STATUS_UPDATE,
                DomainEventType.CODE_CONTEXT_NEEDED: MessageType.CONTEXT_REQUEST,
            }

            message_type = event_to_message_type.get(event.event_type)
            if message_type is None:
                self._logger.system(
                    "unknown_domain_event_type",
                    {"event_type": getattr(event.event_type, "value", str(event.event_type))},
                    level="WARNING",
                )
                return

            recipient_id = (event.metadata or {}).get("recipient_id")

            msg = WebSocketMessage(
                type=message_type,
                timestamp=event.timestamp,
                payload=json_safe(event.payload),
                message_id=None,
                target_client_id=recipient_id,
            )

            def _handle_task_result(task: asyncio.Task) -> None:
                try:
                    exc = task.exception()
                except asyncio.CancelledError:
                    return
                if exc is not None:
                    self._logger.system(
                        "background_task_error",
                        {"source": "handle_domain_event", "error": str(exc)},
                        level="ERROR",
                    )

            if recipient_id:
                task = asyncio.create_task(self._websocket_server.send_to_client(recipient_id, msg))
            else:
                task = asyncio.create_task(self._broadcast_websocket_message(msg))
            task.add_done_callback(_handle_task_result)

        self._controller.register_event_handler(handle_domain_event)

        # WebSocket → Controller (inbound)
        self._setup_websocket_handlers()

        # REST routes → Controller (inbound)
        self._setup_api_routes()

    async def _broadcast_websocket_message(self, msg: WebSocketMessage) -> None:
        try:
            await self._websocket_server.broadcast(msg)
        except Exception as e:
            self._logger.system(
                "error_broadcasting_message",
                {"error": str(e)},
                level="ERROR",
            )

    def _setup_api_routes(self) -> None:
        async def handle_feedback_interaction(request_data: Dict[str, Any]) -> Dict[str, Any]:
            try:
                interaction_data = request_data.get("json", {})
                interaction = FeedbackInteraction.from_dict(interaction_data)
                success = await self._controller.handle_feedback_interaction(interaction)
                return {"status": "received" if success else "failed"}
            except Exception as e:
                self._logger.system(
                    "error_handling_feedback_interaction",
                    {"error": str(e)},
                    level="ERROR",
                )
                return {"status": "error", "error": str(e)}

        async def handle_set_cooldown(request_data: Dict[str, Any]) -> Dict[str, Any]:
            cooldown_seconds = request_data.get("json", {}).get("cooldown_seconds", None)
            if cooldown_seconds is None:
                return {"status": "error", "error": "cooldown_seconds is required"}
            try:
                cooldown_seconds = float(cooldown_seconds)
                if cooldown_seconds < 0:
                    return {"status": "error", "error": "cooldown_seconds must be non-negative"}
                self._controller.set_feedback_cooldown(cooldown_seconds)
                return {"status": "cooldown_set", "cooldown_seconds": cooldown_seconds}
            except (ValueError, TypeError) as e:
                return {"status": "error", "error": f"Invalid cooldown_seconds: {e}"}

        self._rest_api.register_route(
            "/status",
            HttpMethod.GET,
            self._controller.get_system_status,
        )

        self._rest_api.register_route(
            "/feedback/manual_send",
            HttpMethod.GET,
            self._controller.manual_send_feedback,
        )

        self._rest_api.register_route(
            "/feedback/interaction",
            HttpMethod.POST,
            handle_feedback_interaction,
        )

        self._rest_api.register_route(
            "/cooldown",
            HttpMethod.PUT,
            handle_set_cooldown,
        )

    def _setup_websocket_handlers(self) -> None:
        async def on_context_update(message: WebSocketMessage, client_id: str) -> None:
            self._logger.system(
                "context_update_received",
                {"client_id": client_id},
                level="DEBUG",
            )
            ctx = CodeContext.from_dict(message.payload)
            ctx.metadata = {**ctx.metadata, "requester_id": client_id}
            await self._controller.handle_context_update(ctx)

        async def on_ping(message: WebSocketMessage, client_id: str) -> None:
            pong_msg = WebSocketMessage(
                type=MessageType.PONG,
                timestamp=datetime.datetime.now(datetime.timezone.utc).timestamp(),
                payload={},
                message_id=message.message_id,
            )
            await self._websocket_server.send_to_client(client_id, pong_msg)

        self._websocket_server.register_handler(MessageType.CONTEXT_UPDATE, on_context_update)
        self._websocket_server.register_handler(MessageType.PING, on_ping)

    async def _shutdown_handler(self, sig: signal.Signals) -> None:
        self._logger.system("shutdown_signal", {"signal": sig.name})
        await self.stop()
        self._loop.stop()
