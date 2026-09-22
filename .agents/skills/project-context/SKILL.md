---
name: project-context
description: Use on every user turn in the budget repository, including questions, planning, implementation, review, and resumed work, to load project documentation and maintain the AI handoff before finishing.
---

# Project context and handoff

All paths below are relative to the repository root. Apply this routine on every user prompt, not just the first prompt in a session.

## Beginning of each prompt

1. Read `AGENTS.md`, `README.md`, and `AI_HANDOFF.md` from disk. Read all current product/design/UX/plan documents linked under README's Project documents completely; follow additional required context links in the handoff. Do not recursively reload this skill or instructions through documentation links.
2. Inspect `git status --short` and relevant code/diffs. Treat the handoff as context, not proof that work is committed, tested, pushed, or implemented.
3. Reconcile the new request with the active objective, user decisions, pending work, and documented assumptions. The latest explicit user direction takes precedence over older project docs. Continue unfinished work without repeating completed steps.

If a context file is missing, recover facts from existing docs/Git and create the missing handoff. If a read is blocked, disclose the gap and continue only work that does not depend on it. Never invent prior decisions.

## Before finishing each prompt

1. Update canonical docs for changed requirements, design, behavior, setup, verification, and next steps. Keep README's document links current. Do not rewrite unchanged docs just to create a diff.
2. Refresh `AI_HANDOFF.md` even for a question-only or no-change turn. Record the latest request/outcome and say when no product changes occurred. Also checkpoint during long work before a planned pause or context transition when possible.
3. Keep a concise current snapshot with: updated date; objective/current stage; latest changes and paths; confirmed decisions versus proposals; checks actually run and results; blockers; ordered next steps; and local Git/push state. Link detailed docs instead of copying them. Distinguish planned tests from executed tests and local commits from remote publication.
4. Re-read the final diff/status, check documentation links, and ensure the handoff matches observed state. Preserve others' edits and outstanding tasks. Keep credentials, tokens, and private financial data out of docs.

This routine authorizes project documentation maintenance, not unrelated code changes, paid actions, deployment, or pushing to GitHub. If the user explicitly requires a read-only turn, do not write; provide the proposed handoff update in the response. If writes are blocked, report exactly what could not be saved. Do not claim an update succeeded until verified.
