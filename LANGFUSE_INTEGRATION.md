# Langfuse Integration

This document describes the Langfuse observability integration for the ADK agents in this project.

## Overview

[Langfuse](https://langfuse.com) is an LLM observability platform that provides tracing, monitoring, and analytics for AI applications. This project includes optional Langfuse integration for the ADK-based agents (Budget, Weather, Restaurant).

## Current Status: PARTIALLY WORKING

The Langfuse integration is configured and the client authenticates successfully, but **traces are not being exported** due to a known upstream bug.

### What Works
- Langfuse client authentication
- ADK instrumentation initialization
- Agent functionality (unaffected by tracing issues)

### What Doesn't Work
- Trace export to Langfuse dashboard
- OpenTelemetry span completion

## Known Issue: "Failed to detach context"

When the agents process requests, you'll see errors like:

```
Failed to detach context
Traceback (most recent call last):
  File ".../openinference/instrumentation/google_adk/_wrappers.py", line 140, in __aiter__
    yield event
GeneratorExit

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File ".../opentelemetry/context/__init__.py", line 155, in detach
    _RUNTIME_CONTEXT.detach(token)
  File ".../opentelemetry/context/contextvars_context.py", line 53, in detach
    self._current_context.reset(token)
ValueError: <Token var=<ContextVar name='current_context'...> was created in a different Context
```

### Root Cause

This is a conflict between:
1. **OpenTelemetry's context propagation** - Uses Python's `contextvars` for span context
2. **Google ADK's async generators** - The way ADK yields events from async generators
3. **openinference-instrumentation-google-adk** - The auto-instrumentation wrapper

When an async generator is garbage collected or exits early (via `GeneratorExit`), OpenTelemetry attempts to detach context tokens that were created in a different async context, violating Python's `contextvars` design.

### Impact

- **Functionality**: No impact - agents work correctly
- **Tracing**: Spans are created but not properly exported
- **Logs**: Noisy error messages (can be ignored)

## Related GitHub Issues

- [google/adk-python#1670](https://github.com/google/adk-python/issues/1670) - ERROR:opentelemetry.context:Failed to detach context
- [google/adk-python#860](https://github.com/google/adk-python/issues/860) - OpenTelemetry ValueError with ParallelAgent and LlmAgent
- [langfuse/langfuse#8316](https://github.com/langfuse/langfuse/issues/8316) - Conflict between Langfuse's OpenTelemetry instrumentation and Google ADK's context management
- [google/adk-python#501](https://github.com/google/adk-python/issues/501) - Crash while exiting loop agent in adk web

## Configuration

### Environment Variables

Add these to your `.env` file to enable Langfuse:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com  # or https://cloud.langfuse.com for EU
```

### Docker Compose

The following services have Langfuse environment variables configured:
- `budget`
- `restaurant`
- `weather`

### Agent Initialization

Each ADK agent includes a `_init_langfuse()` function that:
1. Checks for Langfuse credentials
2. Initializes the Langfuse client
3. Enables OpenTelemetry instrumentation via `GoogleADKInstrumentor`

## Packages Used

```
langfuse>=2.0.0
openinference-instrumentation-google-adk>=0.1.0
```

## Potential Workarounds (Not Implemented)

### 1. Manual `@observe` Decorator
Instead of auto-instrumentation, manually wrap specific functions:

```python
from langfuse import observe

@observe()
async def invoke(self, query: str, session_id: str) -> str:
    # ... agent logic
```

**Pros**: More control, avoids async generator issues
**Cons**: Requires manual instrumentation of each function

### 2. Suppress Error Logging
Patch the OpenTelemetry context module to suppress errors:

```python
import logging
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)
```

**Pros**: Cleaner logs
**Cons**: Hides potentially useful error information

### 3. Wait for Upstream Fix
Monitor the GitHub issues for fixes in:
- `openinference-instrumentation-google-adk`
- `google-adk`
- `opentelemetry-python`

## Disabling Langfuse

To disable Langfuse integration:

1. Remove or comment out the environment variables in `.env`:
   ```bash
   # LANGFUSE_PUBLIC_KEY=...
   # LANGFUSE_SECRET_KEY=...
   # LANGFUSE_BASE_URL=...
   ```

2. Or remove them from `docker-compose.yml` for the affected services

The agents will detect missing credentials and skip initialization:
```
⚠️  Langfuse credentials not configured, skipping observability
```

## Future Improvements

Once the upstream issues are resolved:
1. Update `openinference-instrumentation-google-adk` to latest version
2. Verify traces appear in Langfuse dashboard
3. Remove this "Known Issue" section from documentation

## References

- [Langfuse Google ADK Integration](https://langfuse.com/integrations/frameworks/google-adk)
- [OpenInference ADK Instrumentation](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-google-adk)
- [Langfuse Documentation](https://langfuse.com/docs)
