---
title: "[Short descriptive title]"
date: "YYYY-MM-DD"
category: "[e.g., security-issues, pipeline-architecture, api-integration, data-quality]"
tags: [tag1, tag2, tag3]
affected_files:
  - execution/script_name.py
  - directives/directive_name.md
directives:
  - directives/directive_name.md
scripts:
  - execution/script_name.py
severity: "[p1, p2, or p3]"
---

# [Title matching frontmatter]

## Problem Statement

[What broke, what was wrong, or what gap was discovered. Be specific — include error messages, symptoms, or the review finding that surfaced it.]

## Investigation

[How you found the root cause. Include what you checked, what you ruled out, and what led to the answer. This helps future investigators facing similar symptoms.]

## Root Cause

[The underlying reason, not just the symptom. One or two sentences. Example: "Scripts were written from scratch without inheriting the path sandboxing helper, so the same vulnerability class recurred in each phase."]

## Fixes Applied

### Fix 1: [Short description]

**Problem:** [What specifically was wrong]

**Solution:** [What you changed and why]

**Files changed:**
- `execution/script_name.py` — [what changed in this file]

### Fix 2: [Short description]

[Repeat as needed for each distinct fix.]

## Prevention Checklist

| Check | What | Why |
|-------|------|-----|
| [When to check] | [What to verify] | [Why this matters — the failure mode it prevents] |
| Before merging new scripts | Verify `_safe_path()` is used for all file operations | Path traversal recurred in 3 consecutive phases when scripts were written without it |
| During code review | Check structured JSON output on all exit paths | Agents can't parse stack traces — silent failures break the orchestration loop |
