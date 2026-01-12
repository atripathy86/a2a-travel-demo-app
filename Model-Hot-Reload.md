# Model Hot-Reload Implementation

This document describes how runtime model selection is implemented in the A2A Travel Demo App.

## Overview

The system allows switching LLM models for each agent at runtime without restarting services. Changes take effect on the next request.

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

**Key Design:** Each A2A agent runs in its own process with its own `ModelConfigManager`. When model changes are requested via the UI, the orchestrator **proxies** the request to the target agent's `/api/models/set` endpoint, ensuring the actual agent process receives the model change.

## Components

### 1. Model Configuration Manager (`agents/model_config.py`)

Central module that manages model configurations for all agents.

**Key Classes:**

- `ModelConfig`: Dataclass representing a single model configuration
- `ModelConfigManager`: Per-agent manager that handles loading, selection, and switching

**Features:**

- Loads model presets from `.env.{agent}.models.json` files
- Supports `${ENV_VAR}` substitution for API keys
- Thread-safe with `threading.RLock`
- Skips models with `_disabled: true`
- Defaults to last non-disabled model in the list

**Key Functions:**

```python
get_model_for_agent(agent_name: str) -> ModelConfig
get_available_models_for_agent(agent_name: str) -> List[ModelConfig]
set_model_for_agent(agent_name: str, model_id: str) -> bool
```

### 2. Model Routes (`agents/model_routes.py`)

FastAPI router that exposes REST endpoints for model management.

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/models/current/{agent}` | GET | Get current model for an agent |
| `/api/models/available/{agent}` | GET | List available models for an agent |
| `/api/models/set` | POST | Set model for an agent |
| `/api/models/all-current` | GET | Get current models for all agents |

**Integration:**

```python
# In orchestrator/agent.py
from model_routes import create_model_routes

agent_names = ["orchestrator", "itinerary", "budget", "restaurant", "weather"]
model_routes = create_model_routes(agent_names)
app.include_router(model_routes)
```

### 3. Next.js API Proxy (`ui/app/api/models/route.ts`)

Proxy route that forwards model API requests from the browser to the orchestrator.

**Why a proxy?**

- Avoids CORS issues when UI runs in Docker
- Browser can't reach internal Docker network (`orchestrator:9000`)
- Single endpoint for all model operations

**Request Mapping:**

| UI Request | Proxied To |
|------------|------------|
| `GET /api/models?agent=X&type=current` | `GET orchestrator:9000/api/models/current/X` |
| `GET /api/models?agent=X&type=available` | `GET orchestrator:9000/api/models/available/X` |
| `GET /api/models?type=all-current` | `GET orchestrator:9000/api/models/all-current` |
| `POST /api/models` | `POST orchestrator:9000/api/models/set` |

### 4. React Hook (`ui/lib/hooks/useModelConfig.ts`)

Custom hook for managing model state in React components.

**State:**

- `currentModels`: Record of current model per agent
- `availableModels`: Record of available models per agent
- `loading`: Loading state per operation
- `error`: Error state per operation

**Actions:**

- `fetchCurrentModel(agent)`: Fetch current model for one agent
- `fetchAvailableModels(agent)`: Fetch available models for one agent
- `fetchAllCurrentModels()`: Fetch current models for all agents
- `setModel(agent, modelId)`: Switch model for an agent

### 5. UI Component (`ui/components/ModelSelector.tsx`)

Collapsible sidebar panel for model selection.

**Features:**

- Displays current model for each agent
- Dropdown to select from available models
- Loading and error states
- Collapsible to save screen space

## Data Flow

### Default Model Selection

When an agent starts, the default model is selected via `ModelConfigManager._initialize_from_env()`:

```
1. Check for agent-specific env var (e.g., ORCHESTRATOR_MODEL=gpt-4o)
2. If env var exists, find matching model by ID in available models
3. If found → use that model as default
4. If NOT found or no env var → use LAST non-disabled model in the JSON array
```

**Key code** (`model_config.py` lines 143-166):

```python
def _initialize_from_env(self) -> None:
    env_var = f"{self.agent_name.upper()}_MODEL"  # e.g., ORCHESTRATOR_MODEL
    selected_model_id = os.getenv(env_var)

    if selected_model_id:
        for model in self._available_models:
            if model.id == selected_model_id:
                self._current_model = model
                return

    # Fallback: use LAST available (non-disabled) model
    if self._available_models:
        self._current_model = self._available_models[-1]
```

**Example**: Given this config file:

```json
{
  "models": [
    { "id": "model-a", "name": "Model A" },
    { "id": "model-b", "name": "Model B" },
    { "id": "model-c", "name": "Model C", "_disabled": true },
    { "id": "model-d", "name": "Model D" }
  ]
}
```

- Default = "Model D" (last non-disabled)
- If `ORCHESTRATOR_MODEL=model-a` is set → "Model A" becomes default

### Loading Models on UI Mount

```
1. ModelSelector mounts
2. useEffect calls fetchAllCurrentModels()
3. Hook calls GET /api/models?type=all-current
4. Proxy forwards to orchestrator
5. ModelConfigManager returns current models
6. UI displays current model for each agent
```

### Switching a Model

```
1. User selects new model from dropdown
2. handleModelChange calls setModel(agent, modelId)
3. Hook calls POST /api/models with {agent, model_id}
4. Proxy forwards to orchestrator
5. ModelConfigManager.set_current_model() updates selection
6. Response includes new model config
7. UI updates to show new selection
```

### Agent Using the Model

#### ADK Agents (orchestrator, budget, weather, restaurant)

ADK agents use `before_model_callback` for runtime model switching per [ADK issue #3647](https://github.com/google/adk-python/issues/3647):

```
1. Agent receives request
2. before_model_callback fires BEFORE LLM call
3. Callback calls get_model_for_agent(agent_name)
4. Callback modifies llm_request.model string
5. LiteLLM routes to correct provider based on model name
6. LLM processes request
```

**Implementation Pattern:**

```python
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from typing import Optional

def _before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    model_config = get_model_for_agent("agent_name")
    if model_config:
        llm_request.model = model_config.model
    return None

agent = LlmAgent(
    model=initial_model,  # Base LiteLLM instance for credentials
    before_model_callback=_before_model_callback,
    ...
)
```

**Key Points:**

- The agent's `model` attribute (LiteLLM instance) handles API connection/credentials
- The `llm_request.model` string tells LiteLLM which specific model to call
- LiteLLM routes to the correct provider based on model name prefixes (e.g., `openai/gpt-4`, `anthropic/claude-3`)

#### LangGraph Agent (itinerary)

The itinerary agent uses LangGraph with ChatOpenAI. Runtime model switching is implemented via a lazy property pattern:

```
1. Agent receives request
2. self.llm property is accessed
3. Property checks if model_config.id changed
4. If changed, recreates ChatOpenAI with new config
5. Returns cached or new LLM instance
6. LLM processes request
```

**Implementation Pattern:**

```python
class ItineraryAgent:
    def __init__(self):
        self._current_model_id: Optional[str] = None
        self._llm: Optional[ChatOpenAI] = None

    @property
    def llm(self) -> ChatOpenAI:
        model_config = get_model_for_agent("itinerary")
        current_id = model_config.id if model_config else None

        if self._llm is None or current_id != self._current_model_id:
            self._llm = self._create_llm(model_config)
            self._current_model_id = current_id

        return self._llm
```

## Configuration File Format

```json
{
  "models": [
    {
      "name": "Display Name",
      "id": "unique-id",
      "model": "provider/model-name",
      "api_base": "http://endpoint:port",
      "api_key": "${API_KEY}",
      "description": "Optional description",
      "_disabled": false
    }
  ]
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name in UI |
| `id` | Yes | Unique identifier |
| `model` | Yes | LiteLLM model string |
| `api_base` | Yes | API endpoint URL |
| `api_key` | Yes | API key (supports `${ENV_VAR}`) |
| `description` | No | Shown in UI |
| `_disabled` | No | Set `true` to hide from selection |

## Docker Integration

Model config files are mounted as volumes for live editing:

```yaml
# docker-compose.yml
volumes:
  - ./.env.orchestrator.models.json:/app/.env.orchestrator.models.json:ro
```

The `model_config.py` detects whether it's running in Docker or locally:

```python
# Checks both /app (Docker) and parent dir (local)
docker_models_file = script_dir / f".env.{agent_name}.models.json"
local_models_file = script_dir.parent / f".env.{agent_name}.models.json"
```

## Limitations

1. **Orchestrator-Centric**: All model management routes are on the orchestrator. Individual agents don't expose their own model endpoints.

2. **No Persistence**: Model selection is in-memory. Restarting an agent resets to the default (last model in config).

## Agent Support Matrix

| Agent | Framework | Runtime Switching | Notes |
|-------|-----------|-------------------|-------|
| orchestrator | ADK | ✅ Yes | Uses `before_model_callback` |
| budget | ADK | ✅ Yes | Uses `before_model_callback` |
| weather | ADK | ✅ Yes | Uses `before_model_callback` |
| restaurant | ADK | ✅ Yes | Uses `before_model_callback` |
| itinerary | LangGraph | ✅ Yes | Uses lazy property with model ID tracking |

## Future Improvements

- Persist model selection to file or database
- Add model health checks before switching
- Support per-request model override via headers
- Add model usage metrics and logging
