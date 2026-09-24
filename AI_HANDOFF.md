# AI handoff

Updated: 2026-09-24. Safe stopping point requested by the user; read current docs and inspect Git before resuming.

Latest request: check yesterday's commit and all project Markdown, continue, then find a good stopping point and update docs. Confirmed September 23 commits `7f2a4e6` (foundation) and `26d5722` (publication documentation). Continued the invitation/verification/recovery slice, verified it, and stopped before PostgreSQL/storage work. No new commit, push, merge, PR or deployment in this turn.

## Active workspace and objective

Build the private budgeting app defined in README/spec/plan. Code is in `C:/Users/bmauricio/Documents/budget/.worktrees/project-foundation`, branch `feat/project-foundation`, HEAD `26d5722`. Original checkout remains on `main` with synchronized docs and its prior uncommitted edits. Continue implementation only in the existing worktree.

Milestone 1 remains partial. Invitations/recovery now work locally; PostgreSQL concurrency, shared private storage and remaining UX gates are unfinished. Milestones 2-8 remain unimplemented. No real financial data, bank/AI/SEO connections or paid services.

## Implemented checkpoint

- Existing foundation: custom Django user, personal/group workspaces, owned manual accounts, explicit grants, central authorization, sharing/removal/leave, login throttling and private/no-store/noindex responses.
- Owner-only invitation creation/revocation with seven-day single-use hashed tokens, intended-email binding, history warning and paginated pending list (20/page).
- New invitees receive a separate one-hour setup email before choosing credentials. Only its bearer can create the verified identity; normal login and explicit Join group remain required. Existing users verify their current email separately. Accepting never shares the joining user's own accounts.
- Django password reset for verified current emails only, one-hour tokens, generic response and shared database send cooldown. Nonempty emails are case-insensitively unique. Existing unverified users with forgotten passwords require operator assistance.
- Membership notices for affected account owners on the accessible group page. Removal revokes that member's shares and pending invitations. Full unread inbox/push remains milestone 5.
- Local console email, synthetic in-memory test email, and environment-configured production SMTP defaults; no actual email provider configured or contacted.

Main paths: `budget/invitations.py`, `budget/invitation_views.py`, models/forms/sharing/views, migrations 0002/0003, invitation/registration templates, `config/settings.py`, `config/urls.py`, `.env.example`, `budget/tests/test_invitations.py`, and `tests/browser/{invitations.spec.ts,server.py}`.

## Verification actually completed

- Baseline 27 Django tests passed. Final suite: **40/40 pass** with `manage.py test --settings=config.test_settings --noinput`.
- Initial nine invitation tests failed on missing routes, then passed. Independent reviewer reproduced an email-squatting flaw and missing email-length validation; each regression failed before its fix. Mailbox proof now precedes identity creation, and both form/service enforce email length. An additional failing regression drove pagination so older pending invitations remain revocable.
- **3/3 Chrome browser checks pass**; after final pagination/screenshot changes, invitation check reran **1/1 pass**. Covers existing sharing/reduced motion, JavaScript-disabled account creation, and JavaScript-disabled invitation setup/signup/login/join/leave. Invitation owner screens checked at 320/360/390/430/768/1024/1440px. Phone and desktop invitation screenshots opened and reviewed.
- Asset build passes: JS 15.42 kB / 4.96 kB gzip; CSS 58.08 kB / 11.29 kB gzip. No new runtime dependency.
- Framework check, migration drift check and production-mode `check --deploy` pass. The production check validates settings only, not PostgreSQL connectivity or SMTP delivery.
- Browser helper uses a separate ignored `.local/browser.sqlite3`, generated ephemeral secret and console-only mail logs. Server stopped and local port closure confirmed. Earlier browser attempts hit a Windows Start-Process environment collision and browser-runner startup/teardown issues; the documented direct Python helper produced the passing runs.
- No PostgreSQL/two-process test, real SMTP, actual-phone/screen-reader check or load benchmark ran. Previous dependency audit evidence is dated September 23 and was not rerun.

See [development guide](docs/development.md) for startup and browser commands. Run migrations before normal local startup; the isolated browser DB has both new migrations, while ordinary development db.sqlite3 may still need 0003.

## Decisions and remaining limits

Preserve Django; Flowbite/Tailwind controls, Motion, Bklit charts and Kokonut interactions; Manus for public SEO only. Preserve phone UX, selective sharing, integer-cents finance and first-release load gates. React is installed but not mounted; chart/Insights components await their milestones.

SQLite remains DEBUG-only and synthetic-only. Existing PostgreSQL 17 service and credentials were not touched. Production delivery uses configurable Django SMTP; setup/recovery/verification email has initial database cooldowns, not a verified production abuse/capacity model. Unique-email migration deliberately refuses duplicates rather than merging identities.

Deferred foundation finding remains: manual-account creation does not increment personal workspace data_revision; fix before derived reports consume it. No unfixed Important/Critical finding remains from this slice's review. In-flight read/revocation guarantees still require the PostgreSQL concurrency gate.

## Ordered next steps

1. Resume in the existing worktree; read docs, inspect the uncommitted changes and current Git state. Do not rebuild the working foundation/invitation flow.
2. Continue milestone 1 with a dedicated PostgreSQL development/test database, two-process session/revocation/invitation checks, shared private storage and remaining UX details. No existing database credentials have been read or guessed.
3. Fix account-creation revision coverage before milestone 2 reporting. Then implement transactions/CSV/timeline; milestones 3-8 remain in the plan.
4. Configure and verify real email delivery, production services, real-device UX and release gates before real-data usage. Manus still needs public pages/domain and source decisions.

## Git and documentation state

HEAD remains `26d5722`, tracking local `origin/feat/project-foundation`; remote was not contacted this turn. Invitation/recovery code, migrations, tests and docs are **uncommitted and unpushed**, including new untracked files; preserve them. Root `main` retains existing dirty docs and .gitignore. Canonical docs/handoff are synchronized between root and worktree. No merge, PR or deployment.

Execution ledger: `.superpowers/sdd/2026-09-22-budget-app/progress.md` (ignored; retain while the milestone is incomplete). It records prior foundation work, review findings, fixes and this stopping point. Python is worktree `.venv/Scripts/python.exe` (3.14.6); Node 22.23.1/npm 10.9.8. PATH python aliases remain unsuitable.
