# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A VS Code extension that monitors editor activity (active file, cursor position, diagnostics) to estimate developer context and deliver AI feedback via LLM. The backend runs as a local Python server; the extension connects over WebSocket and REST.

## Commands

### Backend (Python 3.11+)
```bash
python -m backend.main --config backend/config.yaml   # start backend
python -m backend.main --debug                        # with debug logging
```

### VS Code Extension
```bash
cd vscode-extension
npm run install:all   # installs extension + webview dependencies
npm run compile       # one-shot TypeScript compile
npm run watch         # continuous compile
npm run build         # production build (compiles webview then extension)
npm run lint          # ESLint
npm run test          # extension tests
```

### Webview UI (standalone dev)
```bash
cd vscode-extension/webview-ui
npm run dev           # Vite dev server
npm run build         # production build → build/
```

### Full-stack debug
Use the "Full Stack (Backend + Extension)" compound config in `.vscode/launch.json` (F5 from vscode-extension folder).

## Architecture

```
VS Code Extension → WebSocket (port 8765) → RuntimeController → FeedbackLayer (LLM) → DomainEvent → WebSocket → Extension
                  → REST API (port 8080)  ↗
```

**Backend** (`backend/`) — Python asyncio

| Module | Role |
|--------|------|
| `main.py` | Entry point: CLI args, config loading, logger init, server startup |
| `controller.py` | Central orchestrator: receives `CodeContext`, runs cooldown logic, triggers `FeedbackLayer`, emits `DomainEvent`s |
| `feedback_layer.py` | LLM prompt engineering, TTL cache, rate limiting, in-flight dedup |
| `logger_service.py` | Three log categories: `system` (printed + CSV), `experiment` (CSV), `feedback` (CSV); real-time file output when `log_to_file` is set |
| `api/server.py` | Wires WebSocket + REST + RuntimeController together (`_wire_components`) |
| `api/websocket_server.py` | WebSocket server; routes typed messages to registered handlers |
| `api/rest_api.py` | aiohttp REST server; routes registered via `register_route` |
| `llm/` | Provider abstraction (OpenAI, etc.) |
| `types/` | Shared dataclasses: `CodeContext`, `FeedbackItem`, `DomainEvent`, `SystemConfig` |

**Message flow (inbound):** Extension sends `CONTEXT_UPDATE` over WebSocket → `server.py` handler calls `controller.handle_context_update(CodeContext)` → controller debounces and calls `FeedbackLayer.generate()` → emits `FEEDBACK_READY` `DomainEvent` → `server.py` converts to `FEEDBACK_DELIVERY` WebSocket message → sent back to originating client.

**REST API routes:**
- `GET /status` — system status
- `GET /feedback/manual_send` — trigger feedback immediately
- `POST /feedback/interaction` — log user interaction with a feedback item
- `PUT /cooldown` — update cooldown at runtime

**VS Code Extension** (`vscode-extension/src/`) — TypeScript

| File | Role |
|------|------|
| `extension.ts` | Activation, command registration, WebSocket lifecycle, editor event wiring |
| `context-collector.ts` | Captures `CodeContext` from VS Code APIs (active editor, cursor, diagnostics, visible range) |
| `websocket-client.ts` | Typed WebSocket wrapper; handles reconnect |
| `feedback-renderer.ts` | Inline editor decorations |
| `webview-provider.ts` | Sidebar panel host |
| `api.ts` | REST calls to backend |

**Webview UI** (`vscode-extension/webview-ui/src/`) — React 18 + `@vscode/webview-ui-toolkit`. Communicates with the extension host via `vscode.postMessage`.

## Configuration

Copy `backend/config.example.yaml` → `backend/config.yaml`. The config maps to two dataclasses in `backend/types/config.py`: `FeedbackLayerConfig` and `ControllerConfig`.

Logging writes three CSV files derived from `log_file_path` (e.g. `logs/ai_feedback_generator.log` → `logs/ai_feedback_generator_experiment.csv` etc.) when `log_to_file: true`.
