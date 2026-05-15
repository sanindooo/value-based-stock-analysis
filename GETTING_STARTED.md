# Getting Started

This guide walks you through understanding the DOE (Directive-Orchestration-Execution) framework using the included starter example. The files are already here — read them, run them, then build your own.

## What's Included

A working directive + script pair that fetches weather data for a city:

- `directives/check_weather.md` — the directive (tells the agent what to do)
- `execution/fetch_weather.py` — the execution script (does the deterministic work)

These demonstrate the core DOE pattern. The script uses the [Open-Meteo API](https://open-meteo.com/) which is free and requires no API key.

## Step 1: Understand the Directive

Open `directives/check_weather.md` and read through it. Key things to notice:

- **Goal** — one paragraph explaining what this directive accomplishes
- **Workflow** — exact CLI commands the agent should run
- **Edge Cases** — documented error scenarios so the agent handles them gracefully
- **Notes & Learnings** — empty section that grows as the directive is used (the self-annealing surface)

The directive defines the *what*, not the *how*. It tells the agent which script to run and what inputs/outputs to expect. All intermediate files go in `.tmp/`.

When creating your own directives, start by copying `directives/_template.md`.

## Step 2: Understand the Execution Script

Open `execution/fetch_weather.py` and read through it. Key patterns demonstrated:

- **Structured JSON output** on all paths (success and error) — the agent can parse the result
- **Path sandboxing** (`_safe_path()`) — output is validated to be under `.tmp/`
- **`_error_exit()` helper** — consistent error format with semantic error codes
- **`--mock` flag** — returns sample data without hitting the network (essential for testing)
- **Atomic writes** (`_atomic_write()`) — prevents corrupted output on crash
- **Exit codes** — 0 on success, non-zero on error

When creating your own scripts, start by copying `execution/_template.py`. It includes all security helpers so you don't have to write them from scratch. See `CLAUDE.md` for the full execution script standards.

## Step 3: Run It

Test with mock data first (no network call):

```bash
python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json --mock
```

Then try a real API call:

```bash
python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json
```

Or ask your AI agent:

```
> Check the weather in London
```

The agent will:
1. Read `directives/check_weather.md`
2. Run `execution/fetch_weather.py --city "London" --output .tmp/weather_result.json`
3. Parse the structured JSON output
4. Report the results to you

## Step 4: Self-Anneal

When something breaks (and it will), the self-annealing loop kicks in:

1. **Error happens** — the script returns structured error JSON
2. **Agent reads the error** — the error code tells it what went wrong
3. **Agent fixes the script** — adjusts the code to handle the issue
4. **Agent tests again** — re-runs to verify the fix
5. **Agent updates the directive** — adds the new edge case so it's documented for next time

This is the core development loop. The system gets stronger every time something breaks.

## Step 5: Build Your Own

1. Copy `directives/_template.md` → `directives/your_directive.md`
2. Copy `execution/_template.py` → `execution/your_script.py`
3. Fill in the template sections and remove helpers you don't need
4. Test with `--mock` first, then with real data

## Next Steps

- Add more directives and scripts as your project grows
- Use [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin) for complex multi-step features (see README.md)
- Check `CLAUDE.md` for execution script standards (security, performance, agent-native output patterns)
