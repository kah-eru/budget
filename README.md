# Budget app

A private budgeting app for partners and friends who choose to share finances. Start with a small deployment, with collaboration and scalable code/data access designed into the first release.

Status (2026-09-28): a working preview with synthetic data only, deployed to Render; not a real-data-ready release. Built by milestone:
- **Milestone 1, foundation:** sign-in, private manual accounts, groups, explicit sharing, invitations with mailbox verification (group and standalone), password recovery, membership notices and member removal, a Settings page (username/email/password changes with email notices or confirmation; System/Light/Dark theme).
- **Milestone 2, transactions:** CSV import from a bank export (column mapping, preview, all-or-nothing, same file once, duplicate review, undo; imported amounts read-only), manual USD transactions, per-workspace names/notes, month/year summaries, a searchable Timeline with daily and running totals and a chart, and Timeline CSV export.
- **Milestone 4, categories and budgets:**
  - workspace categories (a standard set, an Overview breakdown, a Timeline filter)
  - rules with preview and opt-in backfill
  - categorize by example (search, tick, keep the keyword as a rule)
  - split transactions, by hand or by a 70/30-style rule
  - monthly/yearly budgets by category or name, in three types (fixed bill, yearly/irregular cost, flexible) with a disposable income estimate
- **Milestone 5, notifications** (email alerts wait on a provider choice):
  - in-app over-budget alerts, once per person, budget and period
  - phone push, off until the owner sets the two push keys
- **Also:** installable to a phone home screen, tab pages prefetched, chart without flashes.

Not started: Plaid bank sync (milestone 3), AI insights (6), statements (7), the release/load gate (8), and the planning tools (9: reports, goals, recurring, net worth). The full suite passes on SQLite, and the feature and concurrency tests pass on a hosted Neon PostgreSQL development database (synthetic data only).

Active implementation: `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation`, branch `feat/project-foundation`. The original checkout remains on `main`; run application commands inside the worktree.

Repository: [kah-eru/budget](https://github.com/kah-eru/budget).

## AI context workflow

[AGENTS.md](AGENTS.md) requires the [project-context skill](.agents/skills/project-context/SKILL.md) on every prompt in this repository. Read the docs and [AI_HANDOFF.md](AI_HANDOFF.md) before work; update affected docs and refresh the handoff before finishing, including no-change turns. The handoff records current decisions, latest changes, actual validation, blockers, and ordered next steps.

This is repository guidance, not a background hook. The skill is stored in Codex's repository skill directory; if discovery has not refreshed, the agent can read its file directly as required by AGENTS.md. [Official skill discovery](https://learn.chatgpt.com/docs/build-skills) and [project instruction loading](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Project documents

- [Product and technical design](docs/superpowers/specs/2026-09-22-budget-app-design.md): requirements, privacy, screens, data model, integrations, and release criteria.
- [Low-fidelity wireframes and user flows](docs/ux-wireframes.md): phone layouts, key journeys, error states, and frontend component mapping.
- [Build plan](docs/superpowers/plans/2026-09-22-budget-app.md): delivery order, proposed files, checks, and expansion triggers.
- [Development setup and verification](docs/development.md): local startup, dependencies, checks, and current limitations.
- [Operations: online preview](docs/operations.md): Render + GitHub Actions + Neon setup for the synthetic-data preview.

## Agreed scope

- A phone-first responsive web app: touch-friendly navigation and forms, readable charts, home-screen installation, and measured interaction performance across mobile and desktop browsers.
- Use Flowbite/Tailwind for standard controls, Motion (motion.dev) for animation, Bklit UI for charts, and Kokonut UI for selected interactive components. Establish low-fidelity layouts and user flows before visual polish; reuse existing components instead of recreating them.
- Keep Django as the backend and use Manus.im for SEO tracking of public pages only. Private finance pages stay authenticated and excluded from indexing/tracking.
- Monthly and yearly spending, a chronological spending timeline, transaction search, and editable purchase details.
- Automatic bank imports and a manual **Sync now** button.
- Custom categories and merchant/name rules for existing and future transactions.
- Merchant/category budgets with in-app and opt-in push notifications; no purchase blocking.
- Each person chooses which accounts to share. Private accounts stay out of group views and totals.
- Statements where supported, with manual PDF upload and CSV import as fallbacks.
- Invite friends from the start to share selected accounts, budgets, and spending views; no automatic access to personal finances.
- Optional API-key-based AI insights about spending patterns and budget progress, with separate consent for sending shared data to an AI provider.
- Scalable module boundaries, multiple web/worker instances, bounded queries, and a measured load-test gate from the first release.
- Requested 2026-09-25 (designed, not built):
  - split transactions and standard categories
  - fixed/irregular/flexible budgets with a disposable-income estimate
  - pie and trend reports
  - goals
  - recurring-bill projection with a cash-flow forecast
  - alerts for approaching limits, bills due and unusual activity, by push or email
  - read-only net worth and investment monitoring
  - loan accounts
  - Details: spec section "Requested additions — 2026-09-25".

The design uses explicit proposed defaults for decisions we have not discussed. Django, the frontend tools above, and Manus for SEO only are user-confirmed. PostgreSQL is the configured backend; development uses a hosted Neon database (free plan, user-chosen) plus opt-in SQLite for fast local checks. Further mounted React components beyond the Timeline chart, shared-edit permissions, alert calculation, hosting and numeric capacity targets are still unverified. Bklit/Kokonut registries are configured, the Timeline chart uses Bklit; Kokonut awaits Insights. Manus, banks and AI remain disconnected; no provider costs or deployment are authorized.
