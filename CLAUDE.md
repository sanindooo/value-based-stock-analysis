# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Start from the template**
When creating a new execution script, always start by copying `execution/_template.py` and removing helpers you don't need. Never write a script from scratch — the same vulnerability classes (SSRF, path traversal, missing structured output) recurred in every build phase when scripts were written without the hardened helpers.

**3. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**4. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

**5. Flag database migrations**
When adding or modifying Alembic migrations, always remind the user to run `docker compose exec backend alembic upgrade head` against the Docker environment. Schema changes that work locally won't be applied to the Docker Postgres volume automatically — the migration must be run explicitly or the app will crash on startup.

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. If the learning is reusable beyond this one directive, write a solution doc in `docs/solutions/` so future plans can find it
6. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `docs/plans/` - Feature implementation plans (created by compound engineering workflow)
- `docs/solutions/` - Documented learnings and fixes, organized by category (e.g. `architecture-patterns/`, `best-practices/`) with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas.
- `docs/brainstorms/` - Early-stage thinking and exploration
- `todos/` - Ephemeral review findings (per-PR, not committed)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Compound Engineering (Optional Workflow)

This project has the Every Compound Engineering plugin installed. It provides a Plan → Work → Review → Compound workflow for building new features. All commands are interactive—they pause and ask for user input at key decision points. Nothing gets written to disk without confirmation.

**When to use it:**
- Building new features or significant enhancements → use `/workflows:plan` first
- Brainstorming an approach → use `/workflows:brainstorm`
- After completing a feature → use `/workflows:compound` to record learnings
- Before merging → use `/workflows:review` for multi-agent code review

**When NOT to use it:**
- Running existing directives (just follow the directive)
- Quick fixes, config changes, one-line patches
- Executing existing scripts in `execution/`
- When the user explicitly says to skip it

**How it connects to the 3-layer architecture:**
- Plans in `docs/plans/` should reference which directives and execution scripts they'll use or create
- Solutions in `docs/solutions/` complement directive updates—directives get the operational fix, solutions get the broader learning
- The self-annealing loop still applies: fix → update tool → test → update directive. Compound adds: → also write a solution doc if the learning is reusable

**On first run:** There are no existing docs/plans/solutions yet. That's fine—the plugin creates directories on demand. The first `/workflows:plan` will research the codebase (including `directives/` and `execution/`) and produce the first plan. Learnings accumulate from there.

**Configuration:** See `compound-engineering.local.md` at the project root for review agent roster and project-specific context passed to all review agents.

## Execution Script Standards

When creating scripts in `execution/`, follow these standards. They were learned across multiple build phases where the same vulnerability classes kept recurring because scripts were written from scratch without a hardened template.

### Agent-Native Output (Must-Have)

Scripts called by agents must produce deterministic, parseable output on all code paths:

- All success paths emit structured JSON to stdout
- All error paths emit JSON with `status`, `error_code`, `message` to stdout before `sys.exit(1)`
- Exit codes: 0 on success, non-zero on error
- Zero results is a valid success: emit `{"status": "success", "count": 0}`, not silence
- If composable (subcommands calling each other): suppress intermediate stdout so only one JSON document per execution

### Security (Must-Have)

- **Path sandboxing**: All file path arguments must resolve under `PROJECT_ROOT/.tmp/`. Validate with `Path.resolve()` before any file operation.
- **SSRF protection**: Validate URLs before HTTP requests — block private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`) and non-HTTP schemes.
- **Formula injection**: Sanitize strings before writing to Google Sheets — prefix with `'` if value starts with `=`, `+`, `-`, or `@`.
- **Injection at substitution boundaries**: Validate ALL interpolated values at the point of substitution, regardless of source (user data, API responses, AI-generated content).
- **File permissions**: Write sensitive files (tokens, PII) with `0o600` via `os.open()` + `os.fdopen()`, not default umask.
- **Response size limits**: Enforce `MAX_RESPONSE_SIZE` on all external HTTP responses.
- **External API response validation**: Validate response schema before consuming — never trust that required keys exist.

### Performance (Should-Have)

- **Hoist expensive resources**: Create API clients, DB connections, HTTP sessions once and pass as parameters — not inside per-item loops.
- **Regex at module level**: Compile all regex patterns as module-level constants, not inside functions.
- **Batch API calls**: Collect all data first, then make one API call — not one call per item.
- **TTL for caches**: Any file that accumulates entries (seen URLs, processed IDs) needs a TTL-based pruning mechanism.

### API Integration Patterns

- **Rate limiting**: Use explicit retry counters in `while` loops — never `continue` in `for` loops for retries.
- **Budget tracking**: Track API credit usage through state files. Add `--dry-run` flags for cost-free testing.
- **Mock mode**: Every script that calls a paid API should support `--mock` for testing without API cost.
- **Incremental saves**: For paid API operations, save results after each item to prevent data loss on crash.
- **Batch discovery**: During self-annealing, look for batch endpoints that replace N+1 individual calls.

### Python Gotchas

These pitfalls recurred across multiple build phases. They're specific to Python scripts running in an agent context:

- **`continue` in `for` loops doesn't retry** — it advances the iterator. Use an explicit retry counter in a `while` loop instead. This is why the rate limiting rule above says "never `continue` in `for` loops for retries."
- **`ThreadPoolExecutor` silently swallows exceptions** — if a future raises, the exception is stored but never surfaced unless you call `future.result()`. Always iterate results or use `as_completed()` with explicit `.result()` calls.
- **`sys.exit(1)` kills the agent process** — agents run scripts as subprocesses, but if imported as a module, `sys.exit()` raises `SystemExit` which can kill the caller. Always emit structured JSON to stdout before exiting, and never `import` execution scripts as modules — run them as subprocesses.

### Why These Rules Exist

Non-obvious context behind the execution standards above:

- **Formula injection — whitespace bypass**: Checking only the first character of a string isn't enough. Google Sheets strips leading whitespace before evaluating, so `"\t=SUM(A1)"` bypasses a naive `startswith("=")` check. The standard requires checking `value.lstrip()[0]`.
- **`os.replace()` over `os.rename()`**: `os.rename()` is not atomic when source and target are on different filesystems and fails silently on some platforms when the target exists. `os.replace()` is guaranteed atomic when the target exists on the same filesystem.
- **PII amplification chain**: Each pipeline step can make data more sensitive (e.g., a company name becomes a domain, becomes an email, becomes a verified contact). Apply security measures proportionally to the current sensitivity level, not just the input sensitivity.
- **Schema drift prevention**: When adding a new data producer to a pipeline, always check that all downstream consumers handle the new fields. Silent breakage from schema drift was discovered in every phase where a producer was added without updating consumers.

## Coding Principles (Karpathy Guidelines)

This project uses the `andrej-karpathy-skills` plugin. When writing or modifying code, follow these principles:

1. **Think Before Coding** — State assumptions explicitly. If multiple interpretations exist, present them — don't pick silently. If something is unclear, stop and ask.
2. **Simplicity First** — Minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code. No error handling for impossible scenarios. If you write 200 lines and it could be 50, rewrite it.
3. **Surgical Changes** — Touch only what you must. Don't "improve" adjacent code. Match existing style. Every changed line should trace directly to the user's request.
4. **Goal-Driven Execution** — Transform tasks into verifiable goals with success criteria. Loop until verified.

These complement the Execution Script Standards above — the standards define *what* to include in scripts, these principles govern *how* to write the code.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.