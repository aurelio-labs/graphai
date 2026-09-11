# Configuration

GraphAI is configured through environment variables.

## `GRAPHAI_LOG_LEVEL`

Controls how much GraphAI logs. Handy when debugging, or for quieting things down in production.

Levels, loudest to quietest:

- `DEBUG` — everything.
- `INFO` — the default.
- `WARNING` — warnings and worse.
- `ERROR` — errors and critical only.
- `CRITICAL` — critical only.

```bash
# hide warnings, e.g. "Function start has no docstring"
export GRAPHAI_LOG_LEVEL=ERROR

# see everything while troubleshooting
export GRAPHAI_LOG_LEVEL=DEBUG

# for a single command
GRAPHAI_LOG_LEVEL=WARNING python my_script.py
```

If you're seeing lines like this:

```
2025-08-16 13:41:54 WARNING graphai.utils Function start has no docstring
```

set the level to `ERROR` to hide them — or better, add the docstring, since function schemas use it as the description an LLM reads.

## Defaults

| Variable | Default | What it does |
|----------|---------|--------------|
| `GRAPHAI_LOG_LEVEL` | `INFO` | Logging verbosity |

## Suggested levels

- **Development:** `DEBUG` or `INFO`.
- **Production:** `WARNING` or `ERROR`.
- **CI:** `ERROR`, so only real problems surface.
