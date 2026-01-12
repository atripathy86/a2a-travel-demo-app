"""
Model Configuration Routes for Starlette (A2A Agents)

Provides Starlette routes for runtime model management in A2A agents.
Similar to model_routes.py but compatible with Starlette instead of FastAPI.
"""

import json
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from model_config import (
    get_model_for_agent,
    get_available_models_for_agent,
    set_model_for_agent,
)


def create_starlette_model_routes(agent_name: str) -> list[Route]:
    """
    Create Starlette routes for model management for a single agent.

    Args:
        agent_name: Name of the agent (e.g., 'itinerary', 'budget')

    Returns:
        List of Starlette Route objects
    """

    async def get_current_model(request: Request) -> JSONResponse:
        model = get_model_for_agent(agent_name)
        if not model:
            return JSONResponse(
                {"error": f"No model configured for agent: {agent_name}"},
                status_code=404,
            )

        return JSONResponse(
            {
                "name": model.name,
                "id": model.id,
                "model": model.model,
                "api_base": model.api_base,
                "api_key": model.api_key,
                "description": model.description,
            }
        )

    async def get_available_models(request: Request) -> JSONResponse:
        models = get_available_models_for_agent(agent_name)
        current = get_model_for_agent(agent_name)

        return JSONResponse(
            {
                "agent": agent_name,
                "models": [
                    {
                        "name": m.name,
                        "id": m.id,
                        "description": m.description,
                        "model": m.model,
                        "api_base": m.api_base,
                    }
                    for m in models
                ],
                "current_model_id": current.id if current else None,
            }
        )

    async def set_model(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        model_id = body.get("model_id")
        if not model_id:
            return JSONResponse({"error": "model_id is required"}, status_code=400)

        success = set_model_for_agent(agent_name, model_id)

        if not success:
            return JSONResponse(
                {"error": f"Model ID '{model_id}' not found for agent '{agent_name}'"},
                status_code=404,
            )

        new_model = get_model_for_agent(agent_name)

        return JSONResponse(
            {
                "success": True,
                "message": f"Model for '{agent_name}' changed to '{new_model.name}'",
                "new_model": {
                    "name": new_model.name,
                    "id": new_model.id,
                    "model": new_model.model,
                    "api_base": new_model.api_base,
                    "api_key": new_model.api_key,
                    "description": new_model.description,
                }
                if new_model
                else None,
            }
        )

    return [
        Route(f"/api/models/current", get_current_model, methods=["GET"]),
        Route(f"/api/models/available", get_available_models, methods=["GET"]),
        Route(f"/api/models/set", set_model, methods=["POST"]),
    ]
