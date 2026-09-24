# Budget app

A private budgeting app for partners and friends who choose to share finances. Start with a small deployment, with collaboration and scalable code/data access designed into the first release.

Status: milestone 1 is in progress. A local Django foundation implements sign-in, private/manual accounts, groups, explicit sharing, invitations with mailbox verification, password recovery, membership notices and member removal. PostgreSQL/concurrency and release checks remain pending; this is not a finished budgeting app or a real-data-ready deployment.

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

The design uses explicit proposed defaults for decisions we have not discussed. Django, the frontend tools above, and Manus for SEO only are user-confirmed. PostgreSQL is the configured deployment backend; local checks currently use opt-in SQLite. Mounted React components, shared-edit permissions, alert calculation, hosting and numeric capacity targets are still unverified. Bklit/Kokonut registries are configured, but their components await charts/Insights. Manus, banks and AI remain disconnected; no provider costs or deployment are authorized.
