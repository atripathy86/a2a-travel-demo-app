# AG-UI + A2A Multi-Agent Communication Demo

A demonstration of Agent-to-Agent (A2A) communication between different AI agent frameworks using the AG-UI Protocol and A2A Middleware.

![Screenshot of a demo](demo.png)

## Quick Start

### Prerequisites

- [Google API Key](https://aistudio.google.com/app/apikey)
- [OpenAI API Key](https://platform.openai.com/api-keys)

### Option 1: Docker (Recommended)

```bash
cp .env.example .env
# Edit .env and add your API keys
docker-compose up --build
```

### Option 2: Local Development

- Requires Node.js 18+ and Python 3.10+.

```bash

# Configure
# Edit .env and add your API keys
cp .env.example .env

# Python agents
cd agents
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..

# Front End
# Install dependencies
npm install
cd ui && npm install && cd ..

#Run Frontend (needs both the ui and agents stood up)
npm run dev
```

### Option 3: ADK Web UI (Agent Debugging)

The ADK Web UI allows interaction with individual ADK agents directly for testing and debugging.

**Local Development:**
```bash
# After setting up Python environment (see Option 2)
npm run dev:adk-web
#OR
cd agents && .venv/bin/adk web --host=0.0.0.0 --port 8080 .
# ADK Web UI available at http://localhost:8080
```

The ADK Web UI lets you select and chat with individual agents (Budget, Weather, Orchestrator) without going through the full application flow.

### Services

Once running, the following services are available:

| Service | URL | Description |
|---------|-----|-------------|
| UI | http://localhost:3000 | Main application |
| ADK Web | http://localhost:8080 | Agent debugging UI |
| Orchestrator | http://localhost:9000 | Coordinates all agents |
| Itinerary Agent | http://localhost:9001 | Creates travel itineraries |
| Budget Agent | http://localhost:9002 | Estimates travel costs |
| Restaurant Agent | http://localhost:9003 | Recommends restaurants |
| Weather Agent | http://localhost:9005 | Provides weather forecasts |

## Runtime Model Selection

The application supports runtime model selection, allowing you to switch LLM models for each agent without restarting services.

### UI Model Selector

A Model Selector panel is available in the right sidebar of the main UI. It allows you to:
- View the currently selected model for each agent
- Switch models from a dropdown of available presets
- Changes take effect immediately on the next request

### Model Configuration Files

Each agent reads its model configuration from a JSON file:

| Agent | Config File |
|-------|-------------|
| Orchestrator | `.env.orchestrator.models.json` |
| Itinerary | `.env.itinerary.models.json` |
| Budget | `.env.budget.models.json` |
| Restaurant | `.env.restaurant.models.json` |
| Weather | `.env.weather.models.json` |

**Setup:**

1. Copy the example template for each agent:
```bash
cp .env.models.json.example .env.orchestrator.models.json
cp .env.models.json.example .env.itinerary.models.json
cp .env.models.json.example .env.budget.models.json
cp .env.models.json.example .env.restaurant.models.json
cp .env.models.json.example .env.weather.models.json
```

2. Edit each file to add your LLM endpoints and API keys.

### Configuration File Format

```json
{
  "models": [
    {
      "name": "Model Display Name",
      "id": "unique-model-id",
      "model": "provider/model-name",
      "api_base": "http://your-llm-endpoint:port",
      "api_key": "${API_KEY}",
      "description": "Optional description",
      "_disabled": false
    }
  ]
}
```

- `name`: Display name shown in the UI dropdown
- `id`: Unique identifier for the model (used in API calls)
- `model`: Model identifier for LiteLLM (e.g., `gpt-4o`, `claude-3-sonnet`, `hosted_vllm/model-name`)
- `api_base`: LLM API endpoint URL
- `api_key`: API key (supports `${ENV_VAR}` substitution from `.env`)
- `description`: Optional description shown in UI
- `_disabled`: Set to `true` to hide model from selection (useful for incompatible models)

**Note:** The last non-disabled model in the list is used as the default.

### Model Management API

The orchestrator exposes REST endpoints for model management. Since each agent runs in its own Docker container with separate processes, the orchestrator **proxies** model change requests to individual agents:

```
UI → POST /api/models/set {agent: "itinerary", model_id: "gpt-4o"}
    ↓
Orchestrator (port 9000)
    ├── agent == "orchestrator" → update local config
    └── agent != "orchestrator" → proxy to agent's /api/models/set
            ↓
        Target Agent ← receives {model_id: "gpt-4o"}
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/models/current/{agent}` | GET | Get current model for an agent |
| `/api/models/available/{agent}` | GET | List available models for an agent |
| `/api/models/set` | POST | Set model for an agent (proxied to target agent) |
| `/api/models/all-current` | GET | Get current models for all agents |

Example: Set model for budget agent
```bash
curl -X POST http://localhost:9000/api/models/set \
  -H "Content-Type: application/json" \
  -d '{"agent": "budget", "model_id": "gpt-4o"}'
```

Individual agents also expose their own model endpoints (used by the orchestrator proxy):
```bash
# Direct access to agent's model endpoint
curl http://localhost:9002/api/models/current
```

### Docker Compose Integration

Model configuration files are mounted as volumes in `docker-compose.yml`, allowing you to modify them without rebuilding containers:

```yaml
volumes:
  - ./.env.orchestrator.models.json:/app/.env.orchestrator.models.json:ro
```

## Usage

Try asking: "Plan a 3-day trip to Tokyo" or "I want to visit New York for 5 days"

The orchestrator will coordinate the agents to:

1. Collect trip requirements (destination, days, people, budget level)
2. Generate an itinerary
3. Provide weather forecast
4. Recommend restaurants for each day
5. Estimate budget and request approval

Agent interactions are visible in the UI with message flow visualization.

## What This Demonstrates

This demo shows how specialized agents built with different frameworks can communicate via the A2A protocol:

### LangGraph Agents (Python + OpenAI)

- **Itinerary Agent** (Port 9001) - Creates day-by-day travel itineraries
- **Restaurant Agent** (Port 9003) - Recommends meal plans

### ADK Agents (Python + Gemini)

- **Budget Agent** (Port 9002) - Estimates travel costs
- **Weather Agent** (Port 9005) - Provides weather forecasts

### Orchestrator

- **Orchestrator Agent** (Port 9000) - Coordinates all agents via A2A middleware

The demo includes multi-framework integration, structured JSON outputs, generative UI components, human-in-the-loop workflows, and real-time message visualization

## Architecture

```
┌──────────────────────────────────────────┐
│ Next.js UI (CopilotKit)                  │
└────────────┬─────────────────────────────┘
             │ AG-UI Protocol
┌────────────┴─────────────────────────────┐
│ A2A Middleware                            │
│ - Routes messages between agents          │
└──────┬───────────────────────────────────┘
       │ A2A Protocol
       │
       ├─────► LangGraph Agents (OpenAI)
       │       ├── Itinerary (9001)
       │       └── Restaurant (9003)
       │
       └─────► ADK Agents (Gemini)
               ├── Budget (9002)
               └── Weather (9005)
       ▲
       │
┌──────┴──────────┐
│ Orchestrator    │
│ (Port 9000)     │
└─────────────────┘
```

## Project Structure

```
a2a-travel-demo-app/
├── ui/                               # Next.js frontend
│   ├── app/
│   │   ├── api/copilotkit/route.ts   # A2A middleware setup
│   │   └── page.tsx                  # Main UI with Model Selector
│   ├── components/
│   │   ├── a2a/                      # A2A message components
│   │   ├── ModelSelector.tsx         # Runtime model selection UI
│   │   ├── travel-chat.tsx           # Chat orchestration
│   │   └── [other UI components]
│   ├── lib/hooks/
│   │   └── useModelConfig.ts         # Model config React hook
│   ├── package.json
│   └── Dockerfile
│
├── agents/                           # Python agents
│   ├── model_config.py               # Shared model configuration manager
│   ├── model_routes.py               # FastAPI routes for orchestrator (with proxy logic)
│   ├── model_routes_starlette.py     # Starlette routes for A2A agents
│   ├── orchestrator/                 # ADK + AG-UI (9000)
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── itinerary/                    # LangGraph + A2A (9001)
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── budget/                       # ADK + A2A (9002)
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── restaurant/                   # LangGraph + A2A (9003)
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── weather/                      # ADK + A2A (9005)
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── .env.models.json.example          # Template for model configuration
├── .env.orchestrator.models.json     # Orchestrator model presets
├── .env.itinerary.models.json        # Itinerary agent model presets
├── .env.budget.models.json           # Budget agent model presets
├── .env.restaurant.models.json       # Restaurant agent model presets
├── .env.weather.models.json          # Weather agent model presets
├── docker-compose.yml
├── package.json
├── CHANGELOG.md                      # Version history and changes
├── Model-Hot-Reload.md               # Detailed model switching documentation
├── Model-Host-Reload.md              # Implementation summary for multi-process model switching
└── .env.example
```

## Technologies

- **Frontend**: Next.js, CopilotKit, AG-UI Client, Tailwind CSS
- **Backend**: Google ADK (Gemini), LangGraph (OpenAI), FastAPI
- **Protocols**: A2A (agent-to-agent), AG-UI (agent-UI)
- **Middleware**: @ag-ui/a2a-middleware

## Troubleshooting

**Agents not connecting?**
Verify all services are running by checking `http://localhost:9000-9005`

**Missing API keys?**
Ensure `.env` contains `GOOGLE_API_KEY` and `OPENAI_API_KEY`

**Python issues?**
Activate the virtual environment: `cd agents && source .venv/bin/activate`

## Known Issues & Fixes

### google-adk Version Compatibility

**Issue:** `ValueError: No function call event found for function responses ids`

This error occurs with newer versions of google-adk (1.22.0+) due to a bug in event history management during nested agent workflows.

**Fix:** Pin google-adk to version 1.21.0 in `agents/requirements.txt`:
```
google-adk==1.21.0
```

**Reference:** [google/adk-python#1805](https://github.com/google/adk-python/issues/1805)

### Gemini 2.5 Pro Function Name Wrapping

**Issue:** `ValueError: Tool 'send_\nmessage_to_a2a_agent' not found`

Gemini 2.5 Pro sometimes generates function call names with newline characters embedded in them, causing tool lookup failures.

**Fix:** Use `gemini-2.0-flash` instead of `gemini-2.5-pro` for the orchestrator agent in `agents/orchestrator/agent.py`:
```python
# model="gemini-2.5-pro",  # Has function name wrapping issue
model="gemini-2.0-flash",  # Using 2.0-flash to avoid the issue
```

### LiteLLM Pydantic Serialization Warnings

**Issue:** When using LiteLLM for multi-model support, you may see warnings like:
```
UserWarning: Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected 10 fields but got 6: Expected `Message`...
  PydanticSerializationUnexpectedValue(Expected `StreamingChoices`...
```

**Cause:** LiteLLM's internal Pydantic models use `del self.field` to remove optional fields, which breaks Pydantic's field tracking during serialization.

**Impact:** These warnings are cosmetic only - functionality is not affected.

**Status:** This is a known LiteLLM bug ([BerriAI/litellm#11759](https://github.com/BerriAI/litellm/issues/11759)). A fix is pending in [PR #16299](https://github.com/BerriAI/litellm/pull/16299). The warnings will disappear once the fix is merged and released.

### AG-UI ADK Streaming Message Warnings

**Issue:** You may see warnings like:
```
🚨 Force-closing unterminated streaming message: a1d0dc28-8f84-477e-bc60-0ac8054e08b7
```

**Cause:** The AG-UI ADK library (`ag_ui_adk`) forcefully closes streaming messages that weren't properly terminated before the agent run completed. This is a safety mechanism to ensure message streams are always properly closed.

**Impact:** Cosmetic only - the message is still delivered correctly to the frontend.

**Status:** This is internal behavior of the `ag_ui_adk` package's `event_translator.py`. The warning appears when there's a timing mismatch between the agent's response completion and the streaming message lifecycle.

## Learn More

- [AG-UI Protocol](https://docs.ag-ui.com)
- [A2A Protocol](https://github.com/agent-matrix/a2a)
- [Google ADK](https://google.github.io/adk-docs/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [CopilotKit](https://docs.copilotkit.ai)

## License

MIT
