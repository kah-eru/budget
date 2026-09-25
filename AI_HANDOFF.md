# AI handoff

Updated: 2026-09-25. Read current docs and inspect Git before resuming.

Latest request (2026-09-25): "now read the md files and continue." Built handoff next-step 1 in the worktree: transaction list with search/filters/cursor paging, workspace month/year periods with a per-month year table, filtered-list Back after edit, and a bottom-nav overlap fix. Committed locally on `feat/project-foundation`; **not pushed** (push only on request). Details: [development guide](docs/development.md#transaction-list-and-yearly-view--september-25).

Earlier the same day: "now commit and push." Pushed `feat/project-foundation` (through `fcee2b6`) and `main` (`9a466d3`) to GitHub `kah-eru/budget` after a credential scan. No PR, merge or deployment.

## Latest slice (2026-09-25)

- `budget/reporting.py`: `visible_transactions()` (visible accounts + workspace overlay), `monthly(user, ws, year)` one grouped query; `spending()` unchanged in behaviour, shares the sum expressions.
- `budget/forms.py::TransactionFilterForm` (q, account, person, start/end; From ≤ To) with `.apply(rows)`. Search matches the original description or this workspace's display name only.
- `budget/views.py`: `transaction_list` at `workspaces/<id>/transactions/` (name `transactions`), 50 rows, keyset cursor `before=YYYY-MM-DD_id`; `period()` parses `?period=YYYY|YYYY-MM`; `annotation_edit` honours a relative `next` (validated with `url_has_allowed_host_and_scheme`).
- Templates: new `transactions.html`, shared `components/transaction_row.html` (also used by `account.html`), period nav + year table in `workspace.html`.
- `assets/app.css`: `html { scroll-padding-bottom: 6rem }` — the fixed bottom nav was covering a submit button once the workspace list got long (caught by the no-JS browser test).
- Verification: 70 tests OK (4 PG-only skipped) on SQLite; `test_reporting` 24/24 on Neon; check + migration drift clean; build CSS 11.72 kB gzip; 4/4 Chrome checks incl. new `tests/browser/transactions.spec.ts`; 360px list and year screenshots reviewed (`.local/transactions-phone.png`, `.local/year-phone.png`). New tests observed failing first. Test server stopped.

## Recent history (2026-09-24)

- User decisions: commit the invitation slice locally; initially skip PostgreSQL, later chose a hosted **Neon** database (free plan; Supabase was the alternative). Neon Auth stays off (Django owns auth). Neon's onboarding script (global CLI, agent skills, MCP, `neon.ts`, `neon deploy`) was not run.
- Built: revision fix, private storage, manual transactions + monthly summary, per-workspace `TransactionAnnotation` (`b6947b9`), apple-design pass (`cf529f6`), PostgreSQL concurrency tests (`50fc9f7`). Installed the `apple-design` skill (source verified only at https://github.com/emilkowalski/skills; an earlier chat citation of skillselion.com was never fetched).
- Neon: project `dry-sea-53765016`, us-west-2, database `budgetdb`, direct host, SSL required. A password the user pasted in chat was reset before use; the new credentials exist only in ignored `.local/neon.env` (moved there from an untracked root `env.txt`), loaded with `. .local/neon-env.sh`. Migrations 0001-0005 applied; synthetic data only.

## Active workspace and objective

Build the private budgeting app defined in README/spec/plan. Code is in `C:/Users/bmauricio/Documents/budget/.worktrees/project-foundation`, branch `feat/project-foundation`, latest code is the 2026-09-25 list/yearly commit. Original checkout stays on `main` with synchronized (uncommitted) docs. Continue implementation only in the worktree.

Milestone 1 is functionally complete except full responsive navigation and mounted React components; PostgreSQL row-locking checks pass on Neon. Milestone 2 has manual transactions, month/year summaries, a filtered transaction list and workspace annotations. Milestones 3-8 unimplemented. No real financial data, bank/AI/SEO connections or paid services.

## Commits this turn (local only)

- `ed793ee` invitations, mailbox verification, password recovery (previously uncommitted work; 40/40 tests at commit).
- `79450be` fix: `sharing.bump_account_data(account)` bumps `data_revision` on the owner's personal workspace and every workspace the account is shared into; called on account creation.
- `11976e8` private default storage: `STORAGES["default"]` FileSystemStorage at `BUDGET_PRIVATE_STORAGE_ROOT` (default ignored `.local/private-files`); no URL route serves it. Local disk only until a host is chosen (milestone 7).
- `5c54c56` `Transaction` model (migration 0004): positive integer cents, DB constraints for amount > 0 and USD-only, classification expense/refund/income/transfer (card payments = transfer), pending flag, description; index (account, posted_on, id). Owner-only add/edit at `workspaces/<ws>/accounts/<acc>/transactions/new/` and `.../<id>/`. `budget/reporting.py::spending()` is the single spending calculation over `visible_accounts`. Workspace page shows this month's posted/pending/income. `budget/templatetags/money.py` `dollars` filter.

- `b6947b9` `TransactionAnnotation` (migration 0005): unique per (transaction, workspace); display name, classification override (null = original), note. `reporting.annotated(qs, workspace)` joins only the active workspace's overlay (`FilteredRelation`); `spending()` uses the effective classification. Owner-only annotation page at `.../transactions/<id>/annotate/` (account rows' Edit link), which links to "Edit original entry". Category deferred to milestone 4.
- `cf529f6` apple-design pass: `:active` press scale (removed under reduced motion), row press background, h1/h2 negative tracking, `prefers-contrast: more` token overrides, bottom-nav `aria-current`, app-formatted date/amount on the annotation page.

## Verification actually completed

- Evening: **54/54** Django tests (two new annotation tests red on missing route first; member-denied test guards the route). Migration drift clean. Build: CSS 11.60 kB gzip. **3/3 Chrome checks** on a restarted server; 360px annotation form/list screenshots (incl. `prefers-contrast: more`) reviewed; no overflow; pressed transform measured 0.97. Server stopped.

- Each new test observed failing first, then passing. Full suite **51/51** (`manage.py test --settings=config.test_settings --noinput`); `check` and `makemigrations --check` clean; asset build passes (CSS 11.43 kB gzip, JS 4.96 kB gzip).
- Plan fixture verified: $100 + $20 − $15 refund, excluding $100 card payment and $200 transfer → 10500 posted cents; $30 pending → 3000. Jan 31/Feb 1 boundary and private-account exclusion from group totals tested. Member cannot add/edit another owner's transactions (404). Sub-cent, zero and negative amounts rejected.
- **3/3 Chrome browser checks pass** (rerun after template changes, on a restarted server). Transaction form, account list and month summary checked at 360px: no horizontal overflow; screenshots reviewed (`.local/txn-*.png` in worktree). Found and fixed: unstyled Type select, Type defaulting to blank. Test server stopped.
- Not run: PostgreSQL, multi-process, real SMTP, actual phones, screen readers, load.

## Decisions and remaining limits

Preserve Django; Flowbite/Tailwind controls, Motion, Bklit charts, Kokonut interactions; Manus for public SEO only; phone UX, selective sharing, integer cents, load gates. React installed but not mounted.

- Annotations are per workspace: personal overrides/notes never reach group totals or pages (tested). Only the account owner annotates. No category yet (milestone 4 adds Category; annotation gains a category FK then).
- Account page still shows newest 100 only; the workspace transaction list has cursor paging. List cursor is not yet invalidated on data-revision change, and there are no filtered totals or category filter yet.
- Manual transactions are user-originated, so owners may edit amounts; imported (CSV/Plaid) amounts must stay read-only per spec.
- Pre-existing UX issue: workspace switcher list grows long on phones with many groups.
- Neon holds synthetic data only. SQLite remains a DEBUG-only fast path. Local PostgreSQL 17 service unused. Neon free plan: 0.5 GB, 100 CU-hours/month, scales to zero (first request after idle is slower).

## Ordered next steps

1. Timeline with (date, id) cursor paging, daily/cumulative series, then CSV import/export, then Bklit charts.
2. UX: collapse the workspace switcher on phones (long list with many groups); apply apple-design springs once Motion drives real transitions (sheets/drawers).
3. Before real data: a separate Neon `production` database/role for real use, email delivery, hosting decision, real-device UX, load test (milestone 8) and release gates.

## Git and documentation state

`origin` (GitHub `kah-eru/budget`) has `main` at `9a466d3` and `feat/project-foundation` at `fcee2b6`. The 2026-09-25 list/yearly slice and its doc updates are local commits on top (worktree) plus a local docs-sync commit on root `main`; neither is pushed. `main` carries the synchronized docs only; application code lives on `feat/project-foundation`. No pull request or merge exists. See [development guide](docs/development.md).

Execution ledger: `.superpowers/sdd/2026-09-22-budget-app/progress.md` (ignored). Python: worktree `.venv/Scripts/python.exe` (3.14.6); Node 22.23.1/npm 10.9.8.
