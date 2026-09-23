# Budget repository instructions

## Required context routine

Use the [project-context skill](.agents/skills/project-context/SKILL.md) on every user prompt in this repository, including question-only turns and resumed sessions. Read its complete instructions directly if it is not yet listed in the skill picker.

Before substantive task work, read `README.md`, `AI_HANDOFF.md`, and every active product/design/UX/plan document listed in README's Project documents. Read from disk each turn so another session's changes are included. Inspect Git status before editing.

Before the final response, update affected canonical docs and refresh `AI_HANDOFF.md` with the latest outcome, verification, blockers, and next steps. For a no-change turn, record that outcome in the handoff without churning unchanged product docs. Follow the skill's explicit read-only/blocked-write handling.

## Project decisions to preserve

Implementation is currently isolated in `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation` on `feat/project-foundation`. Check `AI_HANDOFF.md` before coding; the original checkout on `main` carries synchronized docs, not the application source.

- Use Flowbite/Tailwind for standard controls, Motion for animation, Bklit UI for charts, and Kokonut UI for selected interactions; reuse existing controls and behaviors. The newer frontend choices supersede the earlier Flowbite-only restriction.
- Keep Django as the backend. Use Manus.im for SEO tracking only; private financial content must not enter SEO indexing or tracking.
- Start with low-fidelity wireframes and user flows before visual polish.
- Keep phone UX, selective finance sharing, and load scalability in first-release scope.
- Separate requested features, proposed architecture, implemented behavior, and measured results.
- Keep secrets and private financial records out of docs and Git. Local documentation work does not imply permission to publish, deploy, or spend money.

This file activates a repository-scoped working routine. It does not install hooks or change global agent settings.
