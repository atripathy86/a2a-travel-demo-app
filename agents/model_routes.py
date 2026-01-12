"""
Model Configuration API Routes

Provides FastAPI endpoints for runtime model management.
These routes are added to the main FastAPI app and allow:
- Getting current model configuration for each agent
- Listing available models for each agent
- Setting/switching the model for each agent at runtime
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import httpx

from model_config import (
    ModelConfig,
    get_model_for_agent,
    get_available_models_for_agent,
    set_model_for_agent,
)

AGENT_URLS = {
    "itinerary": os.getenv("ITINERARY_AGENT_URL", "http://itinerary:9001"),
    "budget": os.getenv("BUDGET_AGENT_URL", "http://budget:9002"),
    "restaurant": os.getenv("RESTAURANT_AGENT_URL", "http://restaurant:9003"),
    "weather": os.getenv("WEATHER_AGENT_URL", "http://weather:9005"),
}


# Request/Response models
class ModelConfigResponse(BaseModel):
    """Response model for current model configuration"""

    name: str
    id: str
    model: str
    api_base: str
    api_key: str
    description: str


class AvailableModel(BaseModel):
    """Model information for listing available models"""

    name: str
    id: str
    description: str
    model: str
    api_base: str


class SetModelRequest(BaseModel):
    """Request to change the current model"""

    agent: str
    model_id: str


class SetModelResponse(BaseModel):
    """Response after model change"""

    success: bool
    message: str
    new_model: Optional[ModelConfigResponse] = None


class AvailableModelsResponse(BaseModel):
    """Response with list of available models"""

    agent: str
    models: List[AvailableModel]
    current_model_id: Optional[str] = None


class AllAgentsModelResponse(BaseModel):
    """Response with current models for all agents"""

    agent: str
    current_model: Optional[ModelConfigResponse]


def create_model_routes(agent_names: List[str]) -> APIRouter:
    """
    Create model management routes for the specified agents.

    Args:
        agent_names: List of agent names (e.g., ['orchestrator', 'itinerary', 'budget'])

    Returns:
        APIRouter with model management endpoints
    """
    router = APIRouter(prefix="/api/models", tags=["models"])

    @router.get("/current/{agent}")
    async def get_current_model(agent: str) -> Optional[ModelConfigResponse]:
        """Get current model configuration for specified agent"""
        if agent not in agent_names:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {agent}")

        model = get_model_for_agent(agent)
        if not model:
            raise HTTPException(
                status_code=404, detail=f"No model configured for agent: {agent}"
            )

        return ModelConfigResponse(
            name=model.name,
            id=model.id,
            model=model.model,
            api_base=model.api_base,
            api_key=model.api_key,
            description=model.description,
        )

    @router.get("/available/{agent}")
    async def get_available_models(agent: str) -> AvailableModelsResponse:
        """Get all available models for specified agent"""
        if agent not in agent_names:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {agent}")

        models = get_available_models_for_agent(agent)
        current = get_model_for_agent(agent)

        return AvailableModelsResponse(
            agent=agent,
            models=[
                AvailableModel(
                    name=m.name,
                    id=m.id,
                    description=m.description,
                    model=m.model,
                    api_base=m.api_base,
                )
                for m in models
            ],
            current_model_id=current.id if current else None,
        )

    @router.post("/set")
    async def set_model(request: SetModelRequest) -> SetModelResponse:
        """Set the current model for an agent"""
        if request.agent not in agent_names:
            raise HTTPException(
                status_code=400, detail=f"Unknown agent: {request.agent}"
            )

        if request.agent == "orchestrator":
            success = set_model_for_agent(request.agent, request.model_id)
            new_model = get_model_for_agent(request.agent)
            return SetModelResponse(
                success=True,
                message=f"Model for '{request.agent}' changed to '{new_model.name if new_model else request.model_id}'",
                new_model=ModelConfigResponse(
                    name=new_model.name,
                    id=new_model.id,
                    model=new_model.model,
                    api_base=new_model.api_base,
                    api_key=new_model.api_key,
                    description=new_model.description,
                )
                if new_model
                else None,
            )

        agent_url = AGENT_URLS.get(request.agent)
        if not agent_url:
            raise HTTPException(
                status_code=400,
                detail=f"No URL configured for agent: {request.agent}",
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{agent_url}/api/models/set",
                    json={"model_id": request.model_id},
                )
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Agent {request.agent} rejected model change: {resp.text}",
                    )
                agent_response = resp.json()
                print(f"🔄 Proxied model change to {request.agent}: {request.model_id}")
                return SetModelResponse(
                    success=True,
                    message=agent_response.get(
                        "message", f"Model changed to {request.model_id}"
                    ),
                    new_model=ModelConfigResponse(**agent_response["new_model"])
                    if agent_response.get("new_model")
                    else None,
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to reach agent {request.agent}: {str(e)}",
            )

    @router.get("/all-current")
    async def get_all_current_models() -> dict:
        """Get current models for all agents"""
        result = {}
        for agent in agent_names:
            model = get_model_for_agent(agent)
            if model:
                result[agent] = {
                    "name": model.name,
                    "id": model.id,
                    "model": model.model,
                    "description": model.description,
                }
        return result

    return router
