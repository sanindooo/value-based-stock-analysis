# Directive: [Name]

## Goal

[One paragraph — what this directive accomplishes and why it matters.]

## When to Use

[When should the orchestrator reach for this directive? Include criteria or comparison with other directives if applicable.]

## Inputs

- [Input 1 — what the orchestrator provides and where it comes from]
- [Input 2]

## Outputs

- `.tmp/[output_file]` — [description of what this file contains]
- [Cloud deliverable, if any — e.g., Google Sheet updated with results]

## Workflow

### Step 1: [Action Name]

```bash
python execution/[script_name].py --input .tmp/[input].json --output .tmp/[output].json
```

[Brief explanation of what this step does and what to check before proceeding.]

### Step 2: [Action Name]

```bash
python execution/[script_name].py --input .tmp/[output].json --output .tmp/[final].json
```

[Brief explanation. Include `--dry-run` or `--mock` instructions for steps that cost money.]

## Edge Cases

| Situation | Handling |
|-----------|----------|
| [Describe the scenario] | [What the orchestrator should do] |
| [API rate limit hit] | [Script returns error JSON with `rate_limited` code — wait and retry] |
| [Empty input file] | [Script returns success with count: 0 — report to user, no action needed] |

## Notes & Learnings

[This section starts empty. Update it when you discover API constraints, timing expectations, common errors, better approaches, or anything that would help the next run. This is the self-annealing surface — each run makes the directive stronger.]
