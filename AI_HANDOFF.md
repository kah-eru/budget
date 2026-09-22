# AI handoff

Updated: 2026-09-22 (project date). This is the current snapshot, not an append-only chat transcript. Read it with the current docs and verify Git state at the start of every prompt.

## Objective and current stage

Build a private budgeting web app for the user, their girlfriend, and invited friends who choose to share finances. Current stage: product/design documentation and low-fidelity UX wireframes only. No app code, dependencies, bank connections, AI integration, deployed site, or performance results exist yet.

Latest request: create a skill that reads project docs at the beginning of every prompt, updates docs at the end, and maintains an AI handoff for the next steps.

## Latest changes

- Added [project-context skill](.agents/skills/project-context/SKILL.md) with beginning/end-of-turn context maintenance, no-change handling, and truthful validation/Git reporting.
- Added [AGENTS.md](AGENTS.md) to require the routine for each prompt, even if automatic skill selection does not trigger it.
- Created this handoff and linked the workflow from [README.md](README.md).
- Product implementation has not started; this turn changes the agent workflow only.

## Confirmed user decisions

- USA; initial banks: Wells Fargo, Marcus savings, Chase checking/credit, and Chime. Girlfriend's banks are not yet known.
- Monthly/yearly spending, editable purchase details, custom categories, name-based historical/future rules, statements, automatic sync, and Sync now.
- Merchant/category budget thresholds with in-app and phone push alerts; no blocking card purchases.
- Each person chooses accounts to share. Friends are finance collaborators in the first release, not merely future standalone users.
- Scalable code and concurrent-load handling from the start, a chronological spending timeline, and API-key-based AI insights. No AI-provider preference.
- Good phone UI and responsive behavior are first-release requirements.
- Use Flowbite components; do not recreate existing widgets. Focus on low-fidelity wireframes, UX, and user flow before visual polish.
- Read project docs at the start of every prompt, update affected docs at the end, and always refresh this handoff.

## Canonical context and proposals

- [Design/spec](docs/superpowers/specs/2026-09-22-budget-app-design.md): scope, privacy, AI consent/cost rules, data model, sync/accounting, mobile UX, and capacity targets.
- [UX wireframes](docs/ux-wireframes.md): draft text wireframes, Flowbite mapping, main journeys, and recovery paths. No user usability test or final visual design has been completed.
- [Build plan](docs/superpowers/plans/2026-09-22-budget-app.md): low-fidelity flow review followed by eight implementation milestones. All remain unexecuted.
- Proposed stack: Django/Python, PostgreSQL, Flowbite HTML/JS + Tailwind, shared private storage, and separate operational/AI workers. Django and numeric load targets are recommendations; Flowbite is explicitly user-selected.
- Proposed AI behavior: each requester uses their own encrypted key; account owners separately consent to provider processing; request-driven read-only insights with usage/cost limits. These defaults have not been individually approved.
- Current Plaid research is dated 2026-09-22. Recheck terms/coverage at real integration. Ten created Production Items are shared across the application, and deletion does not restore slots. Marcus transaction coverage and some PDF support still need verification. Exact hosting/AI/provider prices are not committed.

## Verification and limitations

- Prior documentation turns passed relative-link, Markdown fence, and Git whitespace checks; no application tests could run because there is no app.
- PowerShell structural validation passed: skill name/directory match, required frontmatter/body, and metadata length limits. All seven project/instruction documents were readable, their local links resolved, and code fences were balanced. `git diff --check` passed. These checks do not prove future model compliance; no independent behavioral agent test was run.
- The available `python.exe` resolves to a WindowsApps alias that failed to execute; no usable Python installation was found in the standard locations checked. Do not describe Python skill-validator or app-test commands as run successfully.
- Future agents must follow the instructions; no mechanical hook guarantees execution on every model response. Repository instructions provide the persistent trigger, with direct skill loading as a fallback.

## Next steps

1. On the next prompt, read the skill, README, this handoff, and the three canonical documents above; inspect actual Git state and apply any new user direction.
2. Continue the low-fidelity user-flow review. Preserve Flowbite reuse and the privacy boundaries; amend docs for any corrections.
3. When the user asks to implement, use the reviewed design/plan and start milestone 1: project setup, identity, finance-sharing groups, account permissions, and Flowbite shell. Resolve runtime/provider choices as needed, without treating draft decisions as implemented facts.
4. Complete all eight milestones before claiming the requested app is finished. Use Sandbox/synthetic data until the real-data release checks pass.

## Git and external state

- Repository: [kah-eru/budget](https://github.com/kah-eru/budget), local branch `main`, remote `origin` configured.
- Verified baseline before this workflow change: `ad1a9ff` (Flowbite + UX wireframes). Earlier commits: `14c0c60` (phone UI), `71bc0f6` (initial docs).
- This workflow snapshot is local to the repository. Use `git log -1 --oneline` and `git status --short` for its current commit/worktree state; no self-referential commit hash is embedded in this file.
- No push was performed in this conversation. No hosting, paid plan, live-bank, or AI-provider setup has been performed.
- Windows sandbox may require escalation for Git index/commit writes; it was previously granted for local documentation commits. There is a nonfatal warning reading the user's global Git ignore file; preserve that configuration.
