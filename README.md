# Budget app

A private budgeting app for partners and friends who choose to share finances. Start with a small deployment, with collaboration and scalable code/data access designed into the first release.

Status: documentation only. No application, bank connections, hosting, or paid services have been created.

Repository: [kah-eru/budget](https://github.com/kah-eru/budget).

## AI context workflow

[AGENTS.md](AGENTS.md) requires the [project-context skill](.agents/skills/project-context/SKILL.md) on every prompt in this repository. Read the docs and [AI_HANDOFF.md](AI_HANDOFF.md) before work; update affected docs and refresh the handoff before finishing, including no-change turns. The handoff records current decisions, latest changes, actual validation, blockers, and ordered next steps.

This is repository guidance, not a background hook. The skill is stored in Codex's repository skill directory; if discovery has not refreshed, the agent can read its file directly as required by AGENTS.md. [Official skill discovery](https://learn.chatgpt.com/docs/build-skills) and [project instruction loading](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Project documents

- [Product and technical design](docs/superpowers/specs/2026-09-22-budget-app-design.md): requirements, privacy, screens, data model, integrations, and release criteria.
- [Low-fidelity wireframes and user flows](docs/ux-wireframes.md): phone layouts, key journeys, error states, and Flowbite component mapping.
- [Build plan](docs/superpowers/plans/2026-09-22-budget-app.md): delivery order, proposed files, checks, and expansion triggers.

## Agreed scope

- A phone-first responsive web app: touch-friendly navigation and forms, readable charts, home-screen installation, and measured interaction performance across mobile and desktop browsers.
- Use Flowbite/Tailwind components first. Establish low-fidelity layouts and user flows before visual polish; reuse existing components instead of recreating them.
- Monthly and yearly spending, a chronological spending timeline, transaction search, and editable purchase details.
- Automatic bank imports and a manual **Sync now** button.
- Custom categories and merchant/name rules for existing and future transactions.
- Merchant/category budgets with in-app and opt-in push notifications; no purchase blocking.
- Each person chooses which accounts to share. Private accounts stay out of group views and totals.
- Statements where supported, with manual PDF upload and CSV import as fallbacks.
- Invite friends from the start to share selected accounts, budgets, and spending views; no automatic access to personal finances.
- Optional API-key-based AI insights about spending patterns and budget progress, with separate consent for sending shared data to an AI provider.
- Scalable module boundaries, multiple web/worker instances, bounded queries, and a measured load-test gate from the first release.

The design uses explicit proposed defaults for decisions we have not discussed. The stack, shared-edit permissions, alert calculation, hosting approach, and numeric capacity targets are recommendations, not previously approved choices. The user has no AI-provider preference; select one provider/model during implementation after reviewing its API, data policy, and cost. Start with the design document before implementation.
