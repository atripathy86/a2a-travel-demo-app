def __getattr__(name):
    if name == "ItineraryAgent":
        from .agent import ItineraryAgent

        return ItineraryAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
