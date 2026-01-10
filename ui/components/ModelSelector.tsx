"use client";

import { useEffect, useState } from "react";
import { useModelConfig, type Model } from "@/lib/hooks/useModelConfig";

const AGENTS = ["orchestrator", "itinerary", "budget", "restaurant", "weather"];

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  orchestrator: "🎯 Orchestrator",
  itinerary: "📅 Itinerary",
  budget: "💰 Budget",
  restaurant: "🍽️ Restaurant",
  weather: "🌤️ Weather",
};

export function ModelSelector() {
  const { currentModels, availableModels, loading, error, fetchAvailableModels, setModel, fetchAllCurrentModels } =
    useModelConfig();
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [changingAgent, setChangingAgent] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    fetchAllCurrentModels();
    AGENTS.forEach((agent) => {
      fetchAvailableModels(agent);
    });
  }, [fetchAllCurrentModels, fetchAvailableModels]);

  const toggleAgent = (agent: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agent)) {
        next.delete(agent);
      } else {
        next.add(agent);
      }
      return next;
    });
  };

  const handleModelChange = async (agent: string, modelId: string) => {
    setChangingAgent(agent);
    try {
      const success = await setModel(agent, modelId);
      if (!success) {
        console.error(`Failed to change model for ${agent}`);
      }
    } finally {
      setChangingAgent(null);
    }
  };

  return (
    <div className="w-full h-full flex flex-col rounded-lg bg-white/30 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-[#010507] mb-2">Model Selection</h2>
        <p className="text-xs text-[#838389]">Configure models for each agent</p>
      </div>

      <div className="space-y-2 flex-1">
        {AGENTS.map((agent) => {
          const current = currentModels[agent];
          const available = availableModels[agent] || [];
          const isExpanded = expandedAgents.has(agent);
          const isChanging = changingAgent === agent;

          return (
            <div key={agent} className="border border-[#DBDBE5] rounded-lg bg-white/50 overflow-hidden">
              {/* Header */}
              <button
                onClick={() => toggleAgent(agent)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/30 transition-colors"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="text-sm font-medium text-[#010507] flex-shrink-0">
                    {AGENT_DISPLAY_NAMES[agent] || agent}
                  </span>
                  {current && (
                    <span className="text-xs bg-[#1B936F]/10 text-[#1B936F] px-2 py-0.5 rounded truncate">
                      {current.name}
                    </span>
                  )}
                </div>
                <span className={`text-[#57575B] transition-transform ${isExpanded ? "rotate-180" : ""}`}>
                  ▼
                </span>
              </button>

              {/* Dropdown Content */}
              {isExpanded && (
                <div className="border-t border-[#DBDBE5] bg-white/20 p-3 space-y-2 max-h-64 overflow-y-auto">
                  {loading[`${agent}_available`] ? (
                    <div className="text-xs text-[#838389] py-2">Loading models...</div>
                  ) : error[`${agent}_available`] ? (
                    <div className="text-xs text-red-500 py-2">Error loading models</div>
                  ) : available.length === 0 ? (
                    <div className="text-xs text-[#838389] py-2">No models available</div>
                  ) : (
                    available.map((model: Model) => (
                      <button
                        key={model.id}
                        onClick={() => handleModelChange(agent, model.id)}
                        disabled={isChanging || loading[`${agent}_set`]}
                        className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                          current?.id === model.id
                            ? "bg-[#1B936F]/20 border border-[#1B936F] text-[#1B936F] font-medium"
                            : "bg-white/40 border border-[#DBDBE5] text-[#010507] hover:bg-white/60"
                        } ${isChanging ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                      >
                        <div className="flex items-center gap-2">
                          {current?.id === model.id && <span className="text-[#1B936F]">✓</span>}
                          <span className="font-medium">{model.name}</span>
                        </div>
                        {model.description && <div className="text-[#838389] mt-1 ml-6">{model.description}</div>}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Info Section */}
      <div className="mt-6 pt-4 border-t border-[#DBDBE5] text-xs text-[#838389]">
        <p className="mb-2">💡 Model changes take effect immediately on the next request.</p>
        <p>Each agent can use a different model based on your selection.</p>
      </div>
    </div>
  );
}
