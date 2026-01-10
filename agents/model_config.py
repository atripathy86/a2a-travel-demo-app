"""
Model Configuration Management Module

This module provides centralized model configuration management for all agents.
It allows runtime model selection and hot-reloading of model configurations
without requiring agent restarts.

Features:
- Load model presets from agent-specific .env.AGENT.models.json files
- Support environment variable substitution (e.g., ${OPENAI_API_KEY})
- Runtime model selection and switching
- Automatic LLM instance recreation on model change
- Thread-safe configuration management
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class ModelConfig:
    """Represents a single model configuration"""

    name: str
    id: str
    model: str
    api_base: str
    api_key: str
    description: str = ""


class ModelConfigManager:
    """
    Manages model configurations for a specific agent.

    Handles:
    - Loading model presets from agent-specific JSON files
    - Substituting environment variables in API keys
    - Runtime model selection
    - Thread-safe configuration access
    """

    def __init__(self, agent_name: str, project_root: Optional[str] = None):
        """
        Initialize the model configuration manager.

        Args:
            agent_name: Name of the agent (e.g., 'orchestrator', 'itinerary')
            project_root: Root directory of the project (defaults to agent parent directory)
        """
        self.agent_name = agent_name
        self.lock = threading.RLock()

        # Determine project root - check both Docker (/app) and local (parent dir) paths
        if project_root is None:
            script_dir = Path(__file__).parent
            local_models_file = script_dir.parent / f".env.{agent_name}.models.json"
            docker_models_file = script_dir / f".env.{agent_name}.models.json"

            if docker_models_file.exists():
                project_root = str(script_dir)
            elif local_models_file.exists():
                project_root = str(script_dir.parent)
            else:
                project_root = str(script_dir)

        self.project_root = Path(project_root)
        self.models_file = self.project_root / f".env.{agent_name}.models.json"

        # Current model configuration (in-memory)
        self._current_model: Optional[ModelConfig] = None
        self._available_models: List[ModelConfig] = []
        self._load_models_from_file()
        self._initialize_from_env()

    def _resolve_env_variable(self, value: str) -> str:
        """
        Resolve environment variable references like ${VAR_NAME}.

        Args:
            value: String that may contain ${VAR_NAME} patterns

        Returns:
            String with environment variables substituted
        """
        if not value.startswith("${") or not value.endswith("}"):
            return value

        var_name = value[2:-1]  # Extract VAR_NAME from ${VAR_NAME}
        env_value = os.getenv(var_name)

        if env_value is None:
            # Return original if env var not set
            return value

        return env_value

    def _load_models_from_file(self) -> None:
        """Load available models from the agent-specific models JSON file."""
        with self.lock:
            if not self.models_file.exists():
                print(f"Warning: Models file not found: {self.models_file}")
                self._available_models = []
                return

            try:
                with open(self.models_file, "r") as f:
                    data = json.load(f)

                self._available_models = []
                for model_data in data.get("models", []):
                    if model_data.get("_disabled"):
                        continue

                    api_key = self._resolve_env_variable(model_data.get("api_key", ""))

                    config = ModelConfig(
                        name=model_data.get("name", ""),
                        id=model_data.get("id", ""),
                        model=model_data.get("model", ""),
                        api_base=model_data.get("api_base", ""),
                        api_key=api_key,
                        description=model_data.get("description", ""),
                    )
                    self._available_models.append(config)

                print(
                    f"Loaded {len(self._available_models)} models for agent '{self.agent_name}'"
                )

            except json.JSONDecodeError as e:
                print(f"Error parsing models file {self.models_file}: {e}")
                self._available_models = []

    def _initialize_from_env(self) -> None:
        """Initialize current model from environment variables (e.g., ORCHESTRATOR_MODEL)."""
        with self.lock:
            env_var = f"{self.agent_name.upper()}_MODEL"
            selected_model_id = os.getenv(env_var)

            if selected_model_id:
                # Find matching model by ID
                for model in self._available_models:
                    if model.id == selected_model_id:
                        self._current_model = model
                        print(f"Initialized {self.agent_name} with model: {model.name}")
                        return

                print(
                    f"Warning: Model ID '{selected_model_id}' from {env_var} not found in models file"
                )

            # Fallback: use last available model or create from env vars
            if self._available_models:
                self._current_model = self._available_models[-1]
                print(
                    f"Using default model for {self.agent_name}: {self._current_model.name}"
                )
            else:
                # Last resort: construct from individual env vars
                self._current_model = self._construct_from_legacy_env()

    def _construct_from_legacy_env(self) -> Optional[ModelConfig]:
        """
        Construct ModelConfig from legacy environment variables.
        Falls back to: MODEL, API_BASE, API_KEY (global)
        """
        agent_prefix = self.agent_name.upper()

        # Try agent-specific env vars first
        model = os.getenv(f"{agent_prefix}_MODEL") or os.getenv("MODEL")
        api_base = os.getenv(f"{agent_prefix}_API_BASE") or os.getenv("API_BASE", "")
        api_key = os.getenv(f"{agent_prefix}_API_KEY") or os.getenv("API_KEY")

        if not model or not api_key:
            return None

        return ModelConfig(
            name=f"{self.agent_name.title()} Model",
            id="legacy",
            model=model,
            api_base=api_base,
            api_key=api_key,
            description="Legacy environment variable configuration",
        )

    def get_current_model(self) -> Optional[ModelConfig]:
        """Get the currently selected model configuration."""
        with self.lock:
            return self._current_model

    def get_available_models(self) -> List[ModelConfig]:
        """Get all available model configurations."""
        with self.lock:
            return list(self._available_models)

    def set_current_model(self, model_id: str) -> bool:
        """
        Set the current model by ID.

        Args:
            model_id: ID of the model to select

        Returns:
            True if model was found and selected, False otherwise
        """
        with self.lock:
            for model in self._available_models:
                if model.id == model_id:
                    self._current_model = model
                    # Update environment variable for consistency
                    os.environ[f"{self.agent_name.upper()}_MODEL"] = model_id
                    print(f"Changed {self.agent_name} model to: {model.name}")
                    return True

            print(f"Error: Model ID '{model_id}' not found")
            return False

    def reload_models(self) -> None:
        """Reload models from file and reinitialize from env."""
        with self.lock:
            self._load_models_from_file()
            self._initialize_from_env()


# Global model managers for each agent (initialized on demand)
_model_managers: Dict[str, ModelConfigManager] = {}
_managers_lock = threading.Lock()


def get_model_manager(agent_name: str) -> ModelConfigManager:
    """
    Get or create a model manager for the specified agent.

    Args:
        agent_name: Name of the agent

    Returns:
        ModelConfigManager instance for the agent
    """
    global _model_managers

    with _managers_lock:
        if agent_name not in _model_managers:
            _model_managers[agent_name] = ModelConfigManager(agent_name)
        return _model_managers[agent_name]


def get_model_for_agent(agent_name: str) -> Optional[ModelConfig]:
    """Get the current model configuration for an agent."""
    return get_model_manager(agent_name).get_current_model()


def get_available_models_for_agent(agent_name: str) -> List[ModelConfig]:
    """Get all available models for an agent."""
    return get_model_manager(agent_name).get_available_models()


def set_model_for_agent(agent_name: str, model_id: str) -> bool:
    """Set the current model for an agent."""
    return get_model_manager(agent_name).set_current_model(model_id)


def reload_models_for_agent(agent_name: str) -> None:
    """Reload models from file for an agent."""
    get_model_manager(agent_name).reload_models()
