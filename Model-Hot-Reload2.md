# Model Host Reload - Implementation Summary

This document summarizes the implementation of **runtime model switching across all 5 agents** in the A2A Travel Demo App.

## Problem Statement

Each A2A agent runs in a **separate Docker container/process** with its own `ModelConfigManager` instance. Previously, when the UI changed a model, only the orchestrator's local config was updated — the actual agent processes never received the change.

## Solution: Orchestrator Proxy Pattern

The orchestrator now **proxies model change requests** to individual agents via HTTP:

```
UI → POST /api/models/set {agent: "itinerary", model_id: "gpt-4o"}
    ↓
Orchestrator (port 9000)
    ├── agent == "orchestrator" → update local config
    └── agent != "orchestrator" → proxy to agent's /api/models/set
            ↓
        Itinerary (port 9001) ← receives {model_id: "gpt-4o"}
            └── updates its local ModelConfigManager
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  ┌─────────────────┐    ┌──────────────────────────────────┐   │
│  │ ModelSelector   │───▶│ useModelConfig Hook              │   │
│  │ (UI Component)  │    │ - fetchAvailableModels()         │   │
│  └─────────────────┘    │ - fetchCurrentModel()            │   │
│                         │ - setModel()                      │   │
│                         └──────────────┬───────────────────┘   │
│                                        │                        │
│                         ┌──────────────▼───────────────────┐   │
│                         │ /api/models (Proxy Route)        │   │
│                         │ Forwards requests to orchestrator │   │
│                         └──────────────┬───────────────────┘   │
└────────────────────────────────────────┼────────────────────────┘
                                         │ HTTP
┌────────────────────────────────────────▼────────────────────────┐
│                      Orchestrator (FastAPI)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ model_routes.py (APIRouter)                              │   │
│  │ - GET  /api/models/current/{agent}                       │   │
│  │ - GET  /api/models/available/{agent}                     │   │
│  │ - POST /api/models/set → proxies to individual agents    │   │
│  │ - GET  /api/models/all-current                           │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │ model_config.py (ModelConfigManager)                     │   │
│  │ - Loads models from .env.{agent}.models.json             │   │
│  │ - Thread-safe model selection                            │   │
│  │ - Environment variable substitution                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (proxied model changes)
     ┌───────────────────────┼───────────────────────────────┐
     │                       │                               │
     ▼                       ▼                               ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Itinerary   │    │ Budget      │    │ Weather     │    │ Restaurant  │
│ (9001)      │    │ (9002)      │    │ (9005)      │    │ (9003)      │
│ Starlette   │    │ Starlette   │    │ Starlette   │    │ Starlette   │
│ /api/models │    │ /api/models │    │ /api/models │    │ /api/models │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Files Created

### `agents/model_routes_starlette.py`
Starlette routes for A2A agents (they use Starlette, not FastAPI):
- `GET /api/models/current` - Get current model
- `GET /api/models/available` - List available models
- `POST /api/models/set` - Change model (accepts `{"model_id": "..."}`)

## Files Modified

### `agents/Dockerfile`
Added `COPY model_routes_starlette.py ./` to include the new routes module.

### `agents/model_routes.py`
Added proxy logic to forward model changes to individual agents:
- Added `httpx` import for async HTTP requests
- Added `AGENT_URLS` dict populated from environment variables
- Modified `/api/models/set` to proxy non-orchestrator requests to target agent
- Returns actual agent response (not stale local orchestrator data)

### `agents/itinerary/agent.py`
Integrated model routes:
```python
from model_routes_starlette import create_starlette_model_routes

# In main():
app = server.build()
model_routes = create_starlette_model_routes("itinerary")
app.routes.extend(model_routes)
uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level)
```

### `agents/budget/agent.py`
Same integration pattern as itinerary agent.

### `agents/weather/agent.py`
Same integration pattern as itinerary agent.

### `agents/restaurant/agent.py`
Same integration pattern as itinerary agent.

### `agents/orchestrator/agent.py`
- Added `before_model_callback` for runtime model switching
- Refactored model initialization to use `_get_initial_model()`
- Uses `before_model_callback` pattern per ADK recommendation

### `docker-compose.yml`
Added `no_proxy` environment variable to orchestrator:
```yaml
- no_proxy=itinerary,budget,weather,restaurant,localhost,127.0.0.1
```
This prevents corporate proxy from intercepting internal Docker network traffic.

## Key Implementation Details

### Starlette Routes Integration Pattern
Used in all 4 A2A agents (itinerary, budget, weather, restaurant):

```python
# In main():
app = server.build()
model_routes = create_starlette_model_routes("agent_name")
app.routes.extend(model_routes)
print("📡 Model routes added: /api/models/current, /api/models/available, /api/models/set")
uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level)
```

### Orchestrator Proxy Pattern
In `model_routes.py`:

```python
if request.agent == "orchestrator":
    # Update local config
    success = set_model_for_agent(request.agent, request.model_id)
    # ... return response
else:
    # Proxy to agent via httpx
    agent_url = AGENT_URLS.get(request.agent)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{agent_url}/api/models/set",
            json={"model_id": request.model_id}
        )
    # Return actual agent response
```

### ADK Agent Runtime Model Switching
ADK agents (orchestrator, budget, weather, restaurant) use `before_model_callback`:

```python
def _before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    model_config = get_model_for_agent("agent_name")
    if model_config:
        llm_request.model = model_config.model
    return None

agent = LlmAgent(
    model=initial_model,
    before_model_callback=_before_model_callback,
    ...
)
```

### LangGraph Agent Runtime Model Switching
The itinerary agent uses a lazy property pattern:

```python
@property
def llm(self) -> ChatOpenAI:
    model_config = get_model_for_agent("itinerary")
    current_id = model_config.id if model_config else None

    if self._llm is None or current_id != self._current_model_id:
        self._llm = self._create_llm(model_config)
        self._current_model_id = current_id

    return self._llm
```

## Test Commands

```bash
# Test individual agent directly
curl -s http://localhost:9001/api/models/available | python3 -m json.tool

# Test orchestrator proxy to agent
curl -s -X POST http://localhost:9000/api/models/set \
  -H "Content-Type: application/json" \
  -d '{"agent": "itinerary", "model_id": "gpt-4o"}' | python3 -m json.tool

# Verify agent received the change
curl -s http://localhost:9001/api/models/current | python3 -m json.tool
```

## Agent Support Matrix

| Agent | Framework | Port | Runtime Switching | Method |
|-------|-----------|------|-------------------|--------|
| orchestrator | ADK/FastAPI | 9000 | ✅ Yes | `before_model_callback` |
| itinerary | LangGraph/Starlette | 9001 | ✅ Yes | Lazy property pattern |
| budget | ADK/Starlette | 9002 | ✅ Yes | `before_model_callback` |
| restaurant | ADK/Starlette | 9003 | ✅ Yes | `before_model_callback` |
| weather | ADK/Starlette | 9005 | ✅ Yes | `before_model_callback` |

## Limitations

1. **No Persistence**: Model selection is in-memory. Restarting an agent resets to the default (last model in config).

2. **Proxy Latency**: Model changes to non-orchestrator agents require an HTTP round-trip through the orchestrator.

## References

- [ADK Model Switching Issue #3647](https://github.com/google/adk-python/issues/3647)
- [Model-Hot-Reload.md](./Model-Hot-Reload.md) - Detailed implementation documentation
