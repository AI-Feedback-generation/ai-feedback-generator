# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A VS Code extension that uses real-time eye tracking (Tobii hardware) to estimate developer cognitive load, then delivers context-aware AI feedback via LLM. The system has three layers: signal processing (gaze → features), user state scoring (reactive/ML), and feedback generation (OpenAI). It supports reactive (real-time) and proactive (30s-ahead prediction) operation modes.

## Commands

### Backend (Python 3.11+)
```bash
python -m backend.main --config backend/config.yaml   # start backend
python -m backend.training.train_xgboost --config backend/config.yaml --split-dir DIR  # train XGBoost model
```

### VS Code Extension
```bash
cd vscode-extension
npm install:all       # installs extension + webview dependencies
npm run compile       # one-shot TypeScript compile
npm run watch         # continuous compile
npm run build         # production build (includes webview)
npm run lint          # ESLint
npm run test          # extension tests
```

### Webview UI
```bash
cd vscode-extension/webview-ui
npm run dev           # Vite dev server
npm run build         # production build → build/
npm run lint
npm run format        # Prettier
```

### Full-stack debug
Use the "Full Stack (Backend + Extension)" compound config in `.vscode/launch.json` (F5 from vscode-extension folder).

## Architecture

```
Eye Tracker (120 Hz) → Signal Processing (2 Hz features) → Reactive/Forecasting Tool → Feedback Layer (LLM) → VS Code Extension (inline decorations + sidebar)
```

**Backend** (`backend/`) — Python asyncio

| Module | Role |
|--------|------|
| `main.py` | Entry point: CLI args, config loading, server startup |
| `core/runtime_controller.py` | Central orchestrator: state, mode switching, feedback timing/cooldowns |
| `api/server.py` | WebSocket server (port 8765) + REST API (port 8080); wires all components |
| `layers/signal_processing.py` | 1s windows, 0.5s stride; computes fixation/saccade/pupil/IPA features |
| `layers/reactive_tool.py` | Rule-based + ML user state scoring (0–1 cognitive load) |
| `layers/forecasting_tool.py` | XGBoost inference; predicts user state 30s ahead |
| `layers/feedback_layer.py` | LLM prompt engineering, caching, rate limiting |
| `types/config.py` | Dataclass config hierarchy; deserializes `config.yaml` |
| `services/eye_tracker/` | Adapters for Tobii hardware, simulated, and replay modes |
| `training/train_xgboost.py` | Participant-level train/val/test split, model serialization to `models/trained/latest.*` |

**VS Code Extension** (`vscode-extension/src/`) — TypeScript

Key files: `extension.ts` (commands, editor events, WebSocket lifecycle), `WebSocketClient.ts` (typed WS wrapper), `FeedbackRenderer.ts` (inline decorations), `WebviewViewProvider.ts` (sidebar panel host).

**Webview UI** (`vscode-extension/webview-ui/src/`) — React 18 + `@vscode/webview-ui-toolkit`

Communicates with extension host via `vscode.postMessage`. Main components: `StatusPanel`, `FeedbackList`, `Controls`, `ExperimentIDs`.

## Configuration

Copy `config.example.yaml` → `config.yaml` before running the backend. Key config sections: `signal_processing`, `forecasting`, `reactive_tool`, `feedback_layer` (LLM provider/model), `controller` (cooldown, operation mode), `eye_tracker` (Simulated/Replay/Tobii).

## Operation Modes

- **Reactive**: respond to current user state in real time
- **Proactive**: predict state 30s ahead and intervene early
- **Control**: no feedback (baseline)
- **Questionnaire**: UI-only (experiment support)

## Key Dependencies

- **Python**: `tobii-research` (manual wheel install from Tobii SDK), `openai`, `xgboost`, `websockets`, `aiohttp`, `structlog`, `PyWavelets`
- **Extension**: `ws` (WebSocket client), `@types/vscode`
- **Webview**: React 18, `@vscode/webview-ui-toolkit`, Vite 5
