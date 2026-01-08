def __getattr__(name):
    if name == "root_agent":
        from .agent import orchestrator_agent

        return orchestrator_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
