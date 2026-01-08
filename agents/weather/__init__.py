def __getattr__(name):
    if name == "root_agent":
        from .agent import WeatherAgent

        return WeatherAgent()._agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
