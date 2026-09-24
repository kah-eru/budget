# AI handoff

Updated: 2026-09-24 (afternoon). Read current docs and inspect Git before resuming.

Latest request: "there should be ai handoff file and context files for what to do next. can you do it." User decisions this turn: **skip PostgreSQL for now** (no dedicated DB/credentials exist; do not guess them) and **commit the verified invitation slice locally first**. Done: committed it, fixed the deferred account-revision bug, configured private file storage, and started milestone 2 with manual transactions and a monthly spending summary. Local commits only; no push, PR, merge or deployment.

## Active workspace and objective

Build the private budgeting app defined in README/spec/plan. Code is in `C:/Users/bmauricio/Documents/budget/.worktrees/project-foundation`, branch `feat/project-foundation`, latest code commit `5c54c56` (docs commits follow). Original checkout stays on `main` with synchronized (uncommitted) docs. Continue implementation only in the worktree.

Milestone 1 is functionally complete locally except the PostgreSQL two-process gate (deferred by the user; still required before real data), full responsive navigation and mounted React components. Milestone 2 has its first slice. Milestones 3-8 unimplemented. No real financial data, bank/AI/SEO connections or paid services.

## Commits this turn (local only)

- `ed793ee` invitations, mailbox verification, password recovery (previously uncommitted work; 40/40 tests at commit).
- `79450be` fix: `sharing.bump_account_data(account)` bumps `data_revision` on the owner's personal workspace and every workspace the account is shared into; called on account creation.
- `11976e8` private default storage: `STORAGES["default"]` FileSystemStorage at `BUDGET_PRIVATE_STORAGE_ROOT` (default ignored `.local/private-files`); no URL route serves it. Local disk only until a host is chosen (milestone 7).
- `5c54c56` `Transaction` model (migration 0004): positive integer cents, DB constraints for amount > 0 and USD-only, classification expense/refund/income/transfer (card payments = transfer), pending flag, description; index (account, posted_on, id). Owner-only add/edit at `workspaces/<ws>/accounts/<acc>/transactions/new/` and `.../<id>/`. `budget/reporting.py::spending()` is the single spending calculation over `visible_accounts`. Workspace page shows this month's posted/pending/income. `budget/templatetags/money.py` `dollars` filter.

## Verification actually completed

- Each new test observed failing first, then passing. Full suite **51/51** (`manage.py test --settings=config.test_settings --noinput`); `check` and `makemigrations --check` clean; asset build passes (CSS 11.43 kB gzip, JS 4.96 kB gzip).
- Plan fixture verified: $100 + $20 − $15 refund, excluding $100 card payment and $200 transfer → 10500 posted cents; $30 pending → 3000. Jan 31/Feb 1 boundary and private-account exclusion from group totals tested. Member cannot add/edit another owner's transactions (404). Sub-cent, zero and negative amounts rejected.
- **3/3 Chrome browser checks pass** (rerun after template changes, on a restarted server). Transaction form, account list and month summary checked at 360px: no horizontal overflow; screenshots reviewed (`.local/txn-*.png` in worktree). Found and fixed: unstyled Type select, Type defaulting to blank. Test server stopped.
- Not run: PostgreSQL, multi-process, real SMTP, actual phones, screen readers, load.

## Decisions and remaining limits

Preserve Django; Flowbite/Tailwind controls, Motion, Bklit charts, Kokonut interactions; Manus for public SEO only; phone UX, selective sharing, integer cents, load gates. React installed but not mounted.

- Classification currently lives on `Transaction` as the source classification. Spec requires workspace-specific annotations (display name, category, note, classification override) — next slice; reporting must then read the annotation for the active workspace.
- Account page shows newest 100 transactions only (`ponytail:` note in `views.account_detail`); cursor paging arrives with the timeline.
- Manual transactions are user-originated, so owners may edit amounts; imported (CSV/Plaid) amounts must stay read-only per spec.
- Pre-existing UX issue: workspace switcher list grows long on phones with many groups.
- SQLite remains DEBUG/synthetic-only. PostgreSQL 17 service untouched; no credentials read.

## Ordered next steps

1. Milestone 2: `TransactionAnnotation` (per transaction/workspace overlay; private notes never in group views) and switch `reporting.spending()` to the effective classification.
2. Transaction list with search, account/person/date filters, pagination, and a yearly view reusing `spending()`.
3. Timeline with (date, id) cursor paging, daily/cumulative series, then CSV import/export, then Bklit charts.
4. Before real data: user creates a dedicated PostgreSQL dev DB/role (they type the password), then run the two-process session/revocation/invitation checks. Also email delivery, real-device UX and release gates.

## Git and documentation state

Worktree branch `feat/project-foundation` is ahead of local `origin/feat/project-foundation` (`26d5722`) by the September 24 commits (`git log origin/feat/project-foundation..HEAD`); remote not contacted, nothing pushed. Worktree clean. Root `main` retains its prior uncommitted doc edits plus synchronized copies of these canonical docs. See [development guide](docs/development.md).

Execution ledger: `.superpowers/sdd/2026-09-22-budget-app/progress.md` (ignored). Python: worktree `.venv/Scripts/python.exe` (3.14.6); Node 22.23.1/npm 10.9.8.
