"use client";

import { useState, useCallback } from "react";

export interface Model {
  name: string;
  id: string;
  description: string;
  model: string;
  api_base: string;
}

export interface CurrentModel {
  name: string;
  id: string;
  model: string;
  api_base: string;
  api_key: string;
  description: string;
}

export interface UseModelConfigReturn {
  // Current state
  currentModels: Record<string, CurrentModel | null>;
  availableModels: Record<string, Model[]>;
  loading: Record<string, boolean>;
  error: Record<string, string | null>;

  // Actions
  fetchCurrentModel: (agent: string) => Promise<void>;
  fetchAvailableModels: (agent: string) => Promise<void>;
  setModel: (agent: string, modelId: string) => Promise<boolean>;
  fetchAllCurrentModels: () => Promise<void>;
}

/**
 * Hook for managing model configuration across agents
 *
 * Uses Next.js API proxy route (/api/models) to communicate with the orchestrator.
 * This avoids CORS issues and works in both Docker and local development.
 *
 * Provides functions to:
 * - Fetch current model for each agent
 * - Fetch available models for each agent
 * - Switch models at runtime
 * - Load all current models
 */
export function useModelConfig(): UseModelConfigReturn {
  const [currentModels, setCurrentModels] = useState<Record<string, CurrentModel | null>>({});
  const [availableModels, setAvailableModels] = useState<Record<string, Model[]>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, string | null>>({});

  // Fetch current model for a specific agent
  const fetchCurrentModel = useCallback(async (agent: string) => {
    setLoading((prev) => ({ ...prev, [agent]: true }));
    setError((prev) => ({ ...prev, [agent]: null }));

    try {
      const response = await fetch(`/api/models?agent=${encodeURIComponent(agent)}&type=current`);

      if (!response.ok) {
        throw new Error(`Failed to fetch current model: ${response.statusText}`);
      }

      const model = (await response.json()) as CurrentModel;
      setCurrentModels((prev) => ({ ...prev, [agent]: model }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError((prev) => ({ ...prev, [agent]: message }));
      console.error(`Error fetching current model for ${agent}:`, err);
    } finally {
      setLoading((prev) => ({ ...prev, [agent]: false }));
    }
  }, []);

  // Fetch available models for a specific agent
  const fetchAvailableModels = useCallback(async (agent: string) => {
    setLoading((prev) => ({ ...prev, [`${agent}_available`]: true }));
    setError((prev) => ({ ...prev, [`${agent}_available`]: null }));

    try {
      const response = await fetch(`/api/models?agent=${encodeURIComponent(agent)}&type=available`);

      if (!response.ok) {
        throw new Error(`Failed to fetch available models: ${response.statusText}`);
      }

      const data = await response.json();
      setAvailableModels((prev) => ({ ...prev, [agent]: data.models }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError((prev) => ({ ...prev, [`${agent}_available`]: message }));
      console.error(`Error fetching available models for ${agent}:`, err);
    } finally {
      setLoading((prev) => ({ ...prev, [`${agent}_available`]: false }));
    }
  }, []);

  // Set the current model for a specific agent
  const setModel = useCallback(
    async (agent: string, modelId: string): Promise<boolean> => {
      setLoading((prev) => ({ ...prev, [`${agent}_set`]: true }));
      setError((prev) => ({ ...prev, [`${agent}_set`]: null }));

      try {
        const response = await fetch(`/api/models`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            agent,
            model_id: modelId,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to set model: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success && data.new_model) {
          setCurrentModels((prev) => ({ ...prev, [agent]: data.new_model }));
          return true;
        } else {
          throw new Error(data.message || "Failed to set model");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError((prev) => ({ ...prev, [`${agent}_set`]: message }));
        console.error(`Error setting model for ${agent}:`, err);
        return false;
      } finally {
        setLoading((prev) => ({ ...prev, [`${agent}_set`]: false }));
      }
    },
    []
  );

  // Fetch current models for all agents
  const fetchAllCurrentModels = useCallback(async () => {
    const agents = ["orchestrator", "itinerary", "budget", "restaurant", "weather"];

    try {
      setLoading((prev) => ({
        ...prev,
        all_current: true,
      }));

      const response = await fetch(`/api/models?type=all-current`);

      if (!response.ok) {
        throw new Error(`Failed to fetch all current models: ${response.statusText}`);
      }

      const data = await response.json();

      // Update current models for each agent
      const updatedModels: Record<string, CurrentModel | null> = {};
      for (const agent of agents) {
        updatedModels[agent] = data[agent] || null;
      }
      setCurrentModels((prev) => ({ ...prev, ...updatedModels }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      console.error("Error fetching all current models:", err);
      setError((prev) => ({ ...prev, all_current: message }));
    } finally {
      setLoading((prev) => ({
        ...prev,
        all_current: false,
      }));
    }
  }, []);

  return {
    currentModels,
    availableModels,
    loading,
    error,
    fetchCurrentModel,
    fetchAvailableModels,
    setModel,
    fetchAllCurrentModels,
  };
}
