"""
Orchestrator Agent (ADK + AG-UI Protocol)

This agent receives user requests via AG-UI Protocol and delegates tasks
to specialized A2A agents (Itinerary and Budget agents).

The A2A middleware in the frontend will wrap this agent and give it the
send_message_to_a2a_agent tool to communicate with other agents.

Key Components:
- Google ADK (Agent Development Kit) for LLM integration
- AG-UI Protocol for frontend communication
- A2A Protocol for inter-agent communication via middleware
- FastAPI web server for HTTP endpoints
- Runtime model switching via before_model_callback
- Centralized orchestration logic for travel planning workflow

Architecture:
- Acts as the main coordinator for all travel planning tasks
- Delegates specialized tasks to domain-specific agents
- Manages workflow state and inter-agent communication
- Provides human-in-the-loop interactions for critical decisions
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os
import sys
import uvicorn
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore", message="Unclosed connection")

from fastapi import FastAPI

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.models.lite_llm import LiteLlm

sys.path.insert(0, str(Path(__file__).parent.parent))
from model_config import get_model_for_agent


def _get_initial_model():
    """Get initial model for agent creation - uses LiteLLM for flexibility."""
    model_config = get_model_for_agent("orchestrator")

    if model_config:
        kwargs = {"model": model_config.model, "api_key": model_config.api_key}
        if model_config.api_base:
            kwargs["api_base"] = model_config.api_base
        return LiteLlm(**kwargs)

    api_key = os.getenv("API_KEY")
    model_name = os.getenv("MODEL")
    api_base = os.getenv("API_BASE")

    if model_name and api_key:
        kwargs = {"model": model_name, "api_key": api_key}
        if api_base:
            kwargs["api_base"] = api_base
        return LiteLlm(**kwargs)

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        return "gemini-2.0-flash"

    raise ValueError(
        "No model configuration found. Set MODEL + API_KEY (+ optional API_BASE) "
        "for LiteLLM, or GOOGLE_API_KEY for Gemini."
    )


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Runtime model switching callback - modifies LlmRequest before sending to LLM.

    Per ADK recommendation (github.com/google/adk-python/issues/3647):
    - Modify llm_request.model (string) instead of agent.model
    - LiteLLM handles provider routing via model name prefixes
    """
    model_config = get_model_for_agent("orchestrator")

    if model_config:
        llm_request.model = model_config.model
        print(
            f"🎯 Orchestrator using model: {model_config.name} ({model_config.model})"
        )

    return None


orchestrator_agent = LlmAgent(
    name="OrchestratorAgent",
    model=_get_initial_model(),
    before_model_callback=before_model_callback,
    instruction="""
    You are a travel planning orchestrator agent. Your role is to coordinate specialized agents
    to create personalized travel plans.

    AVAILABLE SPECIALIZED AGENTS:

    1. **Itinerary Agent** (LangGraph) - Creates day-by-day travel itineraries with activities
    2. **Restaurant Agent** (LangGraph) - Recommends restaurants for breakfast, lunch, and dinner by day
    3. **Weather Agent** (ADK) - Provides weather forecasts and packing advice
    4. **Budget Agent** (ADK) - Estimates travel costs and creates budget breakdowns

    CRITICAL CONSTRAINTS:
    - You MUST call agents ONE AT A TIME, never make multiple tool calls simultaneously
    - After making a tool call, WAIT for the result before making another tool call
    - Do NOT make parallel/concurrent tool calls - this is not supported

    RECOMMENDED WORKFLOW FOR TRAVEL PLANNING:

    0. **FIRST STEP - Gather Trip Requirements**:
       - Before doing ANYTHING else, call 'gather_trip_requirements' to collect essential trip information
       - Try to extract any mentioned details from the user's message (city, days, people, budget level)
       - Pass any extracted values as parameters to pre-fill the form:
         * city: Extract destination city if mentioned (e.g., "Paris", "Tokyo")
         * numberOfDays: Extract if mentioned (e.g., "5 days", "a week")
         * numberOfPeople: Extract if mentioned (e.g., "2 people", "family of 4")
         * budgetLevel: Extract if mentioned (e.g., "budget", "luxury") -> map to Economy/Comfort/Premium
       - Wait for the user to submit the complete requirements
       - Use the returned values for all subsequent agent calls

    1. **Itinerary Agent** - Create the base itinerary using trip requirements
       - Pass: city, numberOfDays from trip requirements
       - Wait for structured JSON response with day-by-day activities
       - Note: Meals section will be empty initially

    2. **Weather Agent** - Get weather forecast
       - Pass: city and numberOfDays from trip requirements
       - Wait for forecast with daily conditions and packing advice
       - This helps inform activity planning

    3. **Restaurant Agent** - Get meal recommendations
       - Pass: city and numberOfDays from trip requirements
       - Request day-by-day meal recommendations (breakfast, lunch, dinner)
       - Wait for structured JSON with meals matching the itinerary days
       - These will populate the meals section in the itinerary display

    4. **Budget Agent** - Create comprehensive cost estimate
       - Pass: city, numberOfDays, numberOfPeople, budgetLevel from trip requirements
       - Wait for detailed budget breakdown
       - This requires user approval via the request_budget_approval tool
       - You MUST ASK user for approval after the Budget Agent has responded BUT BEFORE using it.

    IMPORTANT WORKFLOW DETAILS:
    - ALWAYS START by calling 'gather_trip_requirements' FIRST before any agent calls
    - The Itinerary Agent creates the structure but leaves meals empty
    - The Restaurant Agent fills in the meals section with specific recommendations
    - The Weather Agent provides context for outdoor activities and what to pack
    - The Budget Agent runs last and requires human-in-the-loop approval.
    - You MUST ASK user for approval after the Budget Agent has responded BUT BEFORE using it.

    TRIP REQUIREMENTS EXTRACTION EXAMPLES:
    - "Plan a trip to Paris" -> call gather_trip_requirements with city: "Paris"
    - "5 day trip to Tokyo for 2 people" -> city: "Tokyo", numberOfDays: 5, numberOfPeople: 2
    - "Budget vacation to Bali" -> city: "Bali", budgetLevel: "Economy"
    - "Luxury 3-day getaway for my family of 4" -> numberOfDays: 3, numberOfPeople: 4, budgetLevel: "Premium"
    - "Plan a trip to New York" -> city: "New York"
    - "I want to visit Rome for a week" -> city: "Rome", numberOfDays: 7

    RESPONSE STRATEGY:
    - After each agent response, briefly acknowledge what you received
    - Build up the travel plan incrementally as you gather information
    - At the end, present a complete, well-organized travel plan
    - Don't just list agent responses - synthesize them into a cohesive plan

    IMPORTANT: Once you have received a response from an agent, do NOT call that same
    agent again for the same information. Use the information you already have.
    """,
)

adk_orchestrator_agent = ADKAgent(
    adk_agent=orchestrator_agent,
    app_name="orchestrator_app",
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
)

app = FastAPI(title="Travel Planning Orchestrator (ADK)")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_adk_fastapi_endpoint(app, adk_orchestrator_agent, path="/")

from model_routes import create_model_routes

agent_names = ["orchestrator", "itinerary", "budget", "restaurant", "weather"]
model_routes = create_model_routes(agent_names)
app.include_router(model_routes)

if __name__ == "__main__":
    if not os.getenv("API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("Warning: No API key found!")
        print("   Set API_KEY (for LiteLLM) or GOOGLE_API_KEY environment variable")
        print("   For LiteLLM, also set MODEL and optionally API_BASE")
        print()

    port = int(os.getenv("ORCHESTRATOR_PORT", 9000))

    print(f"Starting Orchestrator Agent (ADK + AG-UI) on http://localhost:{port}")

    log_level = os.getenv("LOG_LEVEL", "info").lower()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level)
