# Budget app

A private budgeting app for partners and friends who choose to share finances. Start with a small deployment, with collaboration and scalable code/data access designed into the first release.

Status (2026-09-29): a working preview with synthetic data only, deployed to Render; not a real-data-ready release. Built by milestone:
- **Milestone 1, foundation:** sign-in, private manual accounts, groups, explicit sharing, invitations with mailbox verification (group and standalone), password recovery, membership notices and member removal, a Settings page (username/email/password changes with email notices or confirmation; System/Light/Dark theme).
- **Milestone 2, transactions:** CSV import from a bank export (column mapping, preview, all-or-nothing, same file once, duplicate review, undo; imported amounts read-only), manual USD transactions, per-workspace names/notes, month/year summaries, a searchable Timeline with daily and running totals and a chart, compact controls (Graph | List and Filters as icons, with account tick boxes and Select all inside Filters; CSV export from Settings for any workspace and dates), and a **Graph | List** switch where List shows one dated column per account with toggleable lines for transfers between them.
- **Milestone 3, bank sync (sandbox):** Plaid sandbox: connect a bank, choose accounts (private), Sync now, pending→posted kept, card payments as transfers (the bank's own category guess isn't used: categories start empty); automatic sync by signed webhook, Reconnect when the bank needs a new sign-in, a warning when the same bank is connected twice.
- **Milestone 4, categories and budgets:**
  - workspace categories (a standard set, an Overview breakdown, a Timeline filter)
  - rules with preview and opt-in backfill
  - fill a category yourself: pick from every transaction of every account (labelled with its account and where it sits now), confirm moves out of other categories, and tap the words of the name that should send future transactions there
  - split transactions, by hand or by a 70/30-style rule
  - monthly/yearly budgets by category or name, in three types (fixed bill, yearly/irregular cost, flexible) with a disposable income estimate
  - a **Budget tab**: every category's spending against its limit for the month or year (monthly budgets count 12 times in a year), with a page per category for its limit, rules, adding transactions and recent rows; then name-based budgets, the monthly plan, goals and bills
  - **1M | 1Y | Lifetime** on the Overview, the Timeline and the Savings page:
    - calendar month and year; Lifetime goes by month past two years
    - a small bar centered over the chart
    - date labels under it (the period start, and today or "Today" to go back), with faint time markers
    - the Overview and Timeline tabs keep the chosen range
- **Milestone 5, notifications:**
  - in-app over-budget alerts, once per person, budget and period
  - phone push, off until the owner sets the two push keys
  - opt-in email alerts with one-click unsubscribe, off by default; written to the server log until the owner sets up an email provider
- **Milestone 9, planning tools:** net worth (synced balances plus manual items); savings (a header **Spending | Savings** switch that turns both Overview and Timeline to savings accounts, plus a Savings page; savings accounts marked from the bank type or by a switch; money in/out and net saved per month or year, with a chart); recurring bills and income with a 30-day forecast and 3-day bill reminders, optional goals (off until turned on). Reports were dropped by the user.
- **Also:** phone swipes (on the chart, away from its line, for the next or previous month or year; elsewhere between the Timeline, Overview and Budget tabs; Settings is the gear in the header), installable to a phone home screen, tab pages prefetched, charts without flashes, and made-up demo data for the local preview (`tests/browser/seed_demo.py`).

Not started: AI insights (6), statements (7), the release/load gate (8). The full suite passes on SQLite, and the feature and concurrency tests pass on a hosted Neon PostgreSQL development database (synthetic data only).

`main` holds the app (merged 2026-09-28) and Render deploys it. Day-to-day work happens in the worktree `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation` on `feat/project-foundation`, which `main` is fast-forwarded to on each push; run application commands there.

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
- Optional AI insights about spending patterns and budget progress, run only through an API key each person enters themselves (no app or shared key; no key means no AI), with separate consent for sending shared data to an AI provider.
- Scalable module boundaries, multiple web/worker instances, bounded queries, and a measured load-test gate from the first release.
- Requested 2026-09-25, with status as of 2026-09-28:
  - split transactions and standard categories: built
  - fixed/irregular/flexible budgets with a disposable-income estimate: built
  - pie and trend reports: dropped by the user
  - goals: built, off until each person turns them on
  - recurring-bill projection with a cash-flow forecast: built
  - alerts: budget crossing and bills due are built; approaching-limit thresholds and unusual activity are not
  - read-only net worth: built, without investment holdings detail
  - loan accounts: built (synced or manual)
  - Details: spec section "Requested additions — 2026-09-25".
- Requested 2026-09-28 and built: Timeline by account (Graph | List with money lines), a compact Timeline and Overview, and savings (spec sections "Requested — 2026-09-28").

The design uses explicit proposed defaults for decisions we have not discussed. Django, the frontend tools above, and Manus for SEO only are user-confirmed. PostgreSQL is the configured backend; development uses a hosted Neon database (free plan, user-chosen) plus opt-in SQLite for fast local checks. Further mounted React components beyond the Timeline chart, shared-edit permissions, alert calculation, hosting and numeric capacity targets are still unverified. Bklit/Kokonut registries are configured; the Overview, Timeline and Savings charts use Bklit, and Kokonut awaits Insights. Manus and AI remain disconnected. Bank sync works against the free Plaid sandbox only, and on the live site it waits for the owner's Plaid keys in Render. No provider costs are authorized.
