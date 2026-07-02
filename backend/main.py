#!/usr/bin/env python3
"""
AI Feedback Generator Backend - Main Entry Point

Usage:
    python -m backend.main [--config CONFIG_PATH] [--host HOST] [--port PORT]
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for direct script execution
if __name__ == "__main__":
    repo_root = str(Path(__file__).resolve().parent.parent)
    backend_dir = str(Path(__file__).resolve().parent)

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # When running `python main.py` from inside `backend/`, Python can resolve
    # stdlib `types` as local `backend/types` (name shadowing). Remove backend
    # script dir entries to avoid that import collision.
    while backend_dir in sys.path:
        sys.path.remove(backend_dir)
    if Path.cwd().resolve() == Path(backend_dir) and "" in sys.path:
        sys.path.remove("")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Feedback Generator Backend Server"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./backend/config.yaml",
        help="Path to configuration file (YAML)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind servers to",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8765,
        help="WebSocket server port",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8080,
        help="REST API server port",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--system-log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="System log level",
    )
    return parser.parse_args()


def load_config(config_path: str | None) -> "SystemConfig":
    """
    Load configuration from file or use defaults.
    
    Args:
        config_path: Path to configuration file.
        
    Returns:
        System configuration.
    """
    from backend.types import SystemConfig
    from backend.logger_service import get_logger
    
    logger = get_logger()

    if config_path:
        logger.system("config_loading", {"path": config_path})
        return SystemConfig.from_file(config_path)

    logger.system("config_using_defaults", {})
    return SystemConfig()


def setup_logging(debug: bool = False) -> None:
    """
    Set up logging configuration.
    
    Args:
        debug: Enable debug level logging.
    """
    import logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Suppress verbose third-party library logs
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets.server").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


async def run_server(config: "SystemConfig") -> None:
    """
    Run the backend server.

    Args:
        config: System configuration.
    """
    from backend.api.server import Server
    from backend.logger_service import get_logger
    import signal

    server = Server(config)
    logger = get_logger()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.system("shutdown_signal_received", {})
        shutdown_event.set()

    # add_signal_handler is not supported on Windows
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    else:
        # On Windows, we rely on KeyboardInterrupt handling in main()
        pass

    # Keep the server running until interrupted
    try:
        await server.start()
        # Wait for shutdown signal
        await shutdown_event.wait()
    except asyncio.CancelledError:
        logger.system("server_shutdown_requested", {})
    finally:
        await server.stop()

def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    setup_logging(debug=args.debug)
    
    # Initialize logger service with configured levels
    from backend.logger_service import initialize_logger
    logger = initialize_logger(system_level=args.system_log_level)

    # Load configuration
    config = load_config(args.config)

    # Re-initialize logger now that config is loaded, with file output if enabled
    if config.controller.log_to_file and config.controller.log_file_path:
        logger = initialize_logger(
            system_level=args.system_log_level,
            log_base_path=config.controller.log_file_path,
        )

    # Override with command line arguments
    config.controller.websocket_host = args.host
    config.controller.websocket_port = args.ws_port
    config.controller.api_host = args.host
    config.controller.api_port = args.api_port

    logger.system(
        "backend_startup",
        {
            "websocket_url": f"ws://{args.host}:{args.ws_port}",
            "api_url": f"http://{args.host}:{args.api_port}",
            "debug": args.debug,
        },
    )
    
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        logger.system("keyboard_interrupt", {})
        return 0
    except Exception as e:
        logger.system(
            "backend_error",
            {"error": str(e), "error_type": type(e).__name__},
            level="ERROR",
        )
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
