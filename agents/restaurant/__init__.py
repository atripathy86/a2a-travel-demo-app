def __getattr__(name):
    if name == "root_agent":
        from .agent import RestaurantAgent

        return RestaurantAgent()._agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
