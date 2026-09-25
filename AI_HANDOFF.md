# AI handoff

Updated: 2026-09-25. Read current docs and inspect Git before resuming.

Latest request (2026-09-25, "push and go"): pushed budgets, alerts and categorize by example (feat `b583916`, main `6a22d22`), then continued in local commits:
- `c19b967` budget types: fixed (monthly, due day, Paid), yearly/irregular (÷12 set-aside), flexible; Monthly plan (estimate) with disposable income; income entered, or the 3-month posted average.
- `4904ae1` splits: per-workspace lines that add up exactly; reports, category budgets, Timeline filter and CSV count each line; remove restores the single category.
- Verification: 134 Django tests OK; new modules plus concurrency 45/45 on Neon PostgreSQL; 8/8 Chrome checks; screenshots reviewed.
- Pushed 2026-09-25 on "push !"; Render auto-deploys after CI and runs migrations 0010-0011 (live site not checked by the agent).
- Details: [development guide](docs/development.md#budget-types-disposable-income-and-splits--september-25-night-latest).
- Next: rule split templates, phone push (VAPID, no cost), email alerts (the user must choose a provider), CSV import, milestone 9.

Latest request (2026-09-25, categorize by example): search transactions by keyword, pick them, and have same-name transactions count toward that category's limit automatically. The user chose both entry points and "use my search word".
- Built in `ea37c7b`:
  - category → Add transactions: search, tick, keyword rule, no backfill of unticked rows
  - on a transaction: "also similar" with a prefilled, editable keyword that creates the rule and backfills non-manual matches
  - budgets are re-evaluated afterwards
- Verification: 124 Django tests OK; 7/7 Chrome checks; screenshots reviewed.
- Pushed 2026-09-25 on "push and go", together with budgets and alerts (`a95a3d0`, `958ba5e`). Render auto-deploys after CI and runs migrations 0008-0009; live site not checked by the agent.
- Details: [development guide](docs/development.md#categorize-by-example--september-25-night-latest).

Latest (2026-09-25, continuing features after the chart fix): budgets and in-app alerts, in local commits:
- `a95a3d0` budgets: monthly/yearly limit on one category or one name match; posted only, inclusive limit, pending separate; Overview Budgets card.
- `958ba5e` alerts: one per recipient/budget/current period (database unique), silent baselines on budget save or member join, no closed-period alerts, header bell and Alerts inbox with recomputed amounts.
- Verification: 118 Django tests OK; 7/7 Chrome checks; screenshots reviewed.
- Pushed 2026-09-25 with categorize by example (see above).
- Details: [development guide](docs/development.md#budgets-and-in-app-alerts--september-25-night-latest).
- Next: budget kinds (fixed/irregular/flexible) and disposable income, splits, phone push (VAPID keys; no cost), email alerts (the user must choose a provider), CSV import.

Latest request (2026-09-25, chart flash again): "it still is rendering a straight line for like 100ms and then reanimating it on a tab change. fix that and then deploy the fix and then continue with the other features".
- Cause found by per-frame probing at 6x CPU throttle: one fully drawn chart frame painted before the reveal restarted, and the placeholder line showed because the chart took longer than 0.4 s to mount on a throttled CPU.
- Fix: the chart starts in its reveal phase, and the placeholder delay is now 1.5 s. The probe confirms neither shows.
- 7/7 Chrome checks. Pushed to deploy (Render auto-deploys after CI; live site not checked by the agent).
- Details: [development guide](docs/development.md#speed-and-app-feel-pass--september-25-night-latest).
- Next: budgets/limits.

Latest request (2026-09-25, categories): "now continue with the features". Built milestone 4's first part in two local commits:
- `4a58af7` categories: per-workspace, ten seeded standard categories, archive not delete, Overview By category, Timeline filter, CSV column.
- `6927da6` rules: contains/exact with normalized matching, priority then ID, manual choice always wins, preview and opt-in backfill, auto-apply on new/edited transactions.
- Verification: 108 Django tests OK; 7/7 Chrome checks; light/dark 360 px screenshots reviewed.
- Pushed 2026-09-25 on the user's "update all docs and then push and commit"; Render auto-deploys after CI (migrations 0006-0007 run on deploy; live site not checked by the agent).
- Details: [development guide](docs/development.md#categories-and-rules--september-25-night-latest).
- Next: budgets/limits (monthly/yearly per category or name match, overview progress), then in-app notifications. Splits and fixed/irregular/flexible budget kinds are queued after basic limits.

Latest request (2026-09-25, feature list): "make sure the docs have these features as well":
- Requested: bank sync incl. loans, smart categorization and split rules, fixed/irregular/flexible budgets, visual reports, goals, customizable alerts (push/email, approaching limit, bills due, unusual activity), recurring projection, net worth/investments, multi-device, collaborative sharing.
- Already covered: bank sync, manual entry, rules, multi-device, sharing.
- Added to the spec's new "Requested additions — 2026-09-25" section with first defaults. Splits were previously marked "deferred", and net worth/investments were on the deferred list; both are now requested, read-only, no advice.
- Plan: added to milestones 4 and 5, plus a new milestone 9 (reports, goals, recurring, net worth).
- Also updated the README agreed scope and the wireframes placement note.
- Open decisions for the user: Plaid Liabilities/Investments/Balance availability and cost, and an email provider for email alerts.
- Docs only; no code changed. Pushed 2026-09-25 (feat `f3cac84`, main `9475add`); a later "push and commit" found nothing left to commit.

Latest request (2026-09-25, chart flash): "the line flashes before animating itself from left to right, prolly cuz of the preload... remove the preload for only the graph line".
- Frames showed the cause was not the preload: the page crossfade showed the previous page's finished line fading out, plus a brief placeholder line.
- The chart is now excluded from the crossfade, and the placeholder shows only after 0.4 s. Preloading is kept.
- 6/6 Chrome checks. Pushed with the docs update below (live site not checked by the agent).

Latest request (2026-09-25, speed pass): the user asked whether agency speed wins (WebP/AVIF, lazy loading, CDN, trimming scripts, Next.js + headless CMS, SSR) or features (custom categories, limits, notifications) come first, then asked for skeleton loaders and preloading for an app feel. The user chose "speed pass, then features". SSR and lazy loading were already true; images and CMS don't apply.
- Found and fixed a production-only double load of `app.js` (the chart chunk imported the unhashed entry). Initial JS is now 1.17 kB gzip.
- Added a chart skeleton: CLS went from 0.117 to 0.
- Added speculation-rules prefetch (tab switches confirmed served from prefetch), script-gated cross-document view transitions (no-JS Chrome hang avoided), and an installable manifest with icons.
- The font preload was A/B-tested and dropped.
- 93 Django tests OK; 6/6 Chrome checks.
- Pushed 2026-09-25 (feat `4b13f7e`, main `ece145e`); Render auto-deploys after CI (live site not checked by the agent).
- The biggest remaining delay is Render free-plan cold start (a paid plan or keep-warm ping; the user decides, no money spent).
- Details: [development guide](docs/development.md#speed-and-app-feel-pass--september-25-night-latest).
- Next: custom categories (milestone 4), then limits, then notifications.

Latest request (2026-09-25, night, latest): "add some of the settings features, email/password/username change confirmations via email, settings page, export csv, change light/dark mode". User chose **notify after** for password/username (current password required, then a notice to the verified email); email change confirms by a link to the new address. Built Settings (replaces More), username/email changes, CSV export from the Timeline, System/Light/Dark theme. 93 Django tests OK, 6/6 Chrome checks. Pushed 2026-09-25 (feat `2caba84`, main `ec6e9a6`); Render auto-deploys after CI (live site not checked by the agent). Details: [development guide](docs/development.md#settings-login-changes-csv-export-theme--september-25-night-latest). Suggested next settings (not built): sign out other devices, delete account and data, default workspace, two-factor login.

Latest request (2026-09-25, night, later): "make the ui something more like this" (Robinhood reference screenshots). Rebuilt to a flat layout: hero spending number + change vs previous period + bare chart + period chips on Overview and Timeline, stat rows, per-account pink value pills, icon bottom nav, filters in a disclosure; serif/mono fonts and the receipt style removed. 78 Django tests OK, 5/5 Chrome checks, light/dark screenshots reviewed. Pushed on "push" (`feat` cefc49b, `main` 3e16730); Render redeploys after CI (not checked by the agent). Details: [development guide](docs/development.md#robinhood-style-layout--september-25-night-later).

Latest request (2026-09-25, night): "Do the frontend first with these colors" (white + pink light; coffee bean + black cherry dark; more colours coming). Used `frontend-design` + `apple-design`. Built a token theme in `assets/app.css` (palette block -> roles -> Tailwind utilities), self-hosted Young Serif / Hanken Grotesk / Martian Mono, receipt-style spending summaries, OS-driven dark mode; templates moved off gray utilities. 78 Django tests OK, 5/5 Chrome checks, light/dark phone screenshots reviewed. Committed locally; **not pushed**. Details: [development guide](docs/development.md#visual-theme--september-25-night). Next: CSV import/export, then Plaid sandbox (milestone 3).

Latest question (2026-09-25, night): user asked about Plaid and called the frontend generic ("ai slop"), asking why the frontend skills were not used. Answer: Plaid is milestone 3 (after CSV, milestone 2); the UI has only had the low-fidelity pass plus light apple-design touches, and the installed `frontend-design` skill was never used. Offered a visual design pass or starting Plaid sandbox; awaiting their choice. No product changes.

Latest (2026-09-25, night): "continue with the checklist". Built the **Bklit running-total chart** on the Timeline (first mounted React component, lazy chunk 162.56 kB gzip, initial JS 4.63 kB gzip); switched Vite from library mode to a minified app build. 78 Django tests OK, 5/5 Chrome checks, production collectstatic OK. Pushed on the user's "push and commit": `feat/project-foundation` `90f8ad2`, `main` `68d176e`; Render redeploys after CI passes (not checked by the agent). Details: [development guide](docs/development.md#timeline-chart--september-25-night).

Latest (2026-09-25): **preview is live and the owner is signed in** at https://budget-4aek.onrender.com. First deploy failed on a mistyped Render `PGPASSWORD`; fixed by the owner. The owner's site login password appeared in chat; they were told they can change it under More -> Change password. Next: Bklit chart, then CSV import/export (see Ordered next steps; step 1 is done).

Latest (2026-09-25): live preview URL https://budget-4aek.onrender.com (owner-created; duplicate service deleted). Owner declined rotating the chat-exposed `budget_site` password. First user still to be created by the owner; live endpoints not verified by the agent (owner declined the check).

Latest question (2026-09-25): "where do i see the url" — answered (Render dashboard → budget service → URL under the name; live after status shows Live). No product changes.

Latest request (2026-09-25, night): user supplied the Neon site role (file `env (2).txt` in the root checkout, now moved to ignored worktree `.local/neon-site.env`; the password was also pasted in chat, so the user was asked to reset it after setup) and asked whether the GitHub MCP could do the rest. Answer: GitHub is already done (pushed, CI green); Render needs the owner's own sign-in, and a PAT must not go into chat. Created database `budget_site` owned by role `budget_site` and applied migrations 0001-0005. **Still blocked on the owner:** Render Blueprint creation (PG values in the Render dashboard), first user via `createsuperuser` in their own terminal, Neon password reset. Docs-only local commit; not pushed.

Latest request (2026-09-25, evening): "now i want to see this site online. can we use something like github actions". Explained Actions runs CI but cannot host Django. User chose **Render (free)** and **public URL, synthetic data only**. Added Gunicorn/WhiteNoise, proxy-aware settings, `render.yaml`, `.github/workflows/ci.yml`, `.python-version`, and [operations guide](docs/operations.md). Committed and pushed so CI runs and Render can read the Blueprint. **Blocked on the owner:** create a separate Neon role/database, create the Render Blueprint service and enter PG values in the Render dashboard, then create the first user from the PC (steps in the operations guide). No Render service exists yet; nothing is paid.

Latest request (2026-09-25, later): "do it, also if not there already, add the ability to create logins and stuff." Asked about sign-up; the user chose **invite-only + standalone invites** (no public sign-up). Built in the worktree: timeline (daily/cumulative, two-year cap, revision-checked cursor), bottom nav Overview | Timeline | More, collapsible workspace switcher, standalone invites (personal-workspace invitation grants no access), More page with password change. Committed (`43ddb13`) and pushed with the docs sync on `main` when the user asked ("update docs ... then commit and push"); outgoing diffs scanned for credentials, none found. Details: [development guide](docs/development.md#timeline-more-page-and-standalone-invites--september-25-later).

Earlier on 2026-09-25: transaction list/filters/cursor and month/year views (`1be829e`), pushed with docs on the user's "do it".

Earlier the same day: "now commit and push." Pushed `feat/project-foundation` (through `fcee2b6`) and `main` (`9a466d3`) to GitHub `kah-eru/budget` after a credential scan. No PR, merge or deployment.

## Latest slice (2026-09-25, later)

- `budget/reporting.py::daily(rows, start, end)`; `TransactionFilterForm.clean()` resolves a one-month default range and the 731-day cap; `views.transaction_list` adds range totals, daily table, day headers and `rev` cursor restart (`stale`).
- `budget/invitations.py::owned_workspace` (was `owned_group`) allows the owner's personal workspace; `accept_invitation` skips membership for personal invites. Personal wording in `InvitationForm`, `AcceptInvitationForm`, `invitations.html`, `invitation_accept.html` and the email.
- `views.more` + `budget/templates/budget/more.html`; `views.PasswordChange` (`settings/password/`). `page_context` now also returns `personal`. `base.html`: header shows only the username; switcher `<details>`; nav Overview/Timeline/More. CSS `.workspace-summary`.
- Tests: new `budget/tests/test_timeline.py` (4), `StandaloneInvitationTests` (2) and `AccountSettingsTests` (2) in `test_invitations.py`; list tests now pass explicit ranges. 78 OK (4 PG-only skipped) on SQLite; 45/45 of reporting/timeline/invitations on Neon; check and migration drift clean (no migration). Build CSS 11.82 kB gzip. 5/5 Chrome checks, incl. a new JavaScript-disabled standalone-invite journey. Screenshots reviewed: `.local/transactions-phone.png`, `.local/more-phone.png`, `.local/switcher-phone.png`. Test server stopped.

## Previous slice (2026-09-25)

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

Milestone 1 is functionally complete; PostgreSQL row-locking checks pass on Neon. Milestone 2 has manual transactions, month/year summaries, the filtered timeline with a Bklit running-total chart (also on Overview), workspace annotations, and the pink/coffee-bean Robinhood-style UI. Milestones 3-8 unimplemented. No real financial data, bank/AI/SEO connections or paid services.

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

Preserve Django; Flowbite/Tailwind controls, Motion, Bklit charts, Kokonut interactions; Manus for public SEO only; phone UX, selective sharing, integer cents, load gates. React mounted only for the Timeline chart.

- Annotations are per workspace: personal overrides/notes never reach group totals or pages (tested). Only the account owner annotates. No category yet (milestone 4 adds Category; annotation gains a category FK then).
- Account page still shows newest 100 only; the workspace transaction list has cursor paging. List cursor is not yet invalidated on data-revision change, and there are no filtered totals or category filter yet.
- Manual transactions are user-originated, so owners may edit amounts; imported (CSV/Plaid) amounts must stay read-only per spec.
- Workspace switcher is now a one-line `<details>` disclosure; with JavaScript disabled it still works (native).
- Standalone invites: any signed-in user can invite from their personal workspace; the 20/hour-per-workspace and 1/minute-per-address limits apply.
- Neon holds synthetic data only. SQLite remains a DEBUG-only fast path. Local PostgreSQL 17 service unused. Neon free plan: 0.5 GB, 100 CU-hours/month, scales to zero (first request after idle is slower).

## Ordered next steps

1. Done 2026-09-25: Render preview live, owner signed in. Optional: try a synthetic invite (link appears in Render Logs).
2. Done and pushed 2026-09-25: Bklit chart, Settings, CSV export, speed/app-feel pass, chart flash fix. Next per user: custom categories, then limits (budgets), then notifications (in-app inbox first). CSV import still open (imported amounts read-only per spec). Optional: trim the chart chunk (mostly React DOM + Motion).
3. Optional login follow-ups not built: web-based first-user setup (still `createsuperuser`). Apply apple-design springs once Motion drives real transitions.
4. Before real data: a separate Neon `production` database/role for real use, email delivery, hosting decision, real-device UX, load test (milestone 8) and release gates.

## Git and documentation state

Both branches are pushed to `origin` (GitHub `kah-eru/budget`) through the chart flash fix and this docs update (2026-09-25). Each push to `feat/project-foundation` auto-deploys the Render preview after CI. Older handoff entries marked "not pushed" have since been pushed. No PR or merge. `main` carries the synchronized docs only; application code lives on `feat/project-foundation`. No pull request or merge exists. See [development guide](docs/development.md).

Execution ledger: `.superpowers/sdd/2026-09-22-budget-app/progress.md` (ignored). Python: worktree `.venv/Scripts/python.exe` (3.14.6); Node 22.23.1/npm 10.9.8.
