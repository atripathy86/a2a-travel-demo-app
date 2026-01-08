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
│   │   └── page.tsx                  # Main UI
│   ├── components/
│   │   ├── a2a/                      # A2A message components
│   │   ├── travel-chat.tsx           # Chat orchestration
│   │   └── [other UI components]
│   ├── package.json
│   └── Dockerfile
│
├── agents/                           # Python agents
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
├── docker-compose.yml
├── package.json
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

## Learn More

- [AG-UI Protocol](https://docs.ag-ui.com)
- [A2A Protocol](https://github.com/agent-matrix/a2a)
- [Google ADK](https://google.github.io/adk-docs/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [CopilotKit](https://docs.copilotkit.ai)

## License

MIT
