# AI Feedback Generator

A VS Code extension that monitors editor activity to deliver context-aware AI feedback.

## Requirements

- Python 3.11+
- Node.js 18+
- VS Code 1.85+
- An OpenAI API key

## Setup & Running

### 1. Backend

```bash
# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy and edit the config
cp backend/config.example.yaml backend/config.yaml

# Start the backend
python -m backend.main --config backend/config.yaml
```

The backend starts a WebSocket server (default port 8765) and a REST API (default port 8080).

### 2. VS Code Extension

```bash
cd vscode-extension
npm run install:all   # installs extension + webview dependencies
npm run build         # production build
```

Then open the `vscode-extension` folder in VS Code and press **F5** to launch the Extension Development Host.

### 3. Connect

1. Open the command palette and run **"Eye Tracking: Connect to Backend"**
2. Run **"Eye Tracking: Connect Eye Tracker"**
3. Open a code file — feedback will appear automatically based on your eye-tracking state

## Configuration

Copy `backend/config.example.yaml` to `backend/config.yaml`. All options:

### `feedback_layer` — LLM settings

| Option | Default | Description |
|--------|---------|-------------|
| `llm_provider` | `openai` | LLM provider: `openai` or `development` (no LLM calls, for testing) |
| `llm_model` | `gpt-4o-mini` | Model name, e.g. `gpt-4o`, `gpt-4o-mini` |
| `llm_api_key` | `null` | API key — or set via `OPENAI_API_KEY` env var |
| `max_feedback_items` | `1` | Number of feedback items generated per trigger |
| `max_message_length` | `200` | Maximum character length per feedback message |
| `enable_cache` | `true` | Cache LLM responses to reduce API calls |
| `cache_ttl_seconds` | `300.0` | How long cached responses are reused |
| `max_generations_per_minute` | `10` | Rate limit for LLM calls |
| `max_tokens` | `500` | Max tokens per LLM response |
| `temperature` | `0.3` | LLM sampling temperature (0 = deterministic, 1 = creative) |

### `controller` — Runtime settings

| Option | Default | Description |
|--------|---------|-------------|
| `operation_mode` | `reactive` | Operation mode: `reactive` (respond to current state), `proactive` (predict 30s ahead), `control` (no feedback), `questionnaire` (UI only) |
| `feedback_cooldown_seconds` | `60.0` | Minimum seconds between automatic feedback deliveries |
| `websocket_host` | `localhost` | WebSocket server host |
| `websocket_port` | `8765` | WebSocket server port |
| `api_host` | `localhost` | REST API host |
| `api_port` | `8080` | REST API port |
| `log_level` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `log_to_file` | `true` | Whether to write logs to CSV files |
| `log_file_path` | `logs/ai_feedback_generator.log` | Base path for log files — three files are written alongside it: `_experiment.csv`, `_system.csv`, `_feedback.csv` |
