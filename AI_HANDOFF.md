# AI handoff

Updated: 2026-09-28. Read current docs and inspect Git before resuming.

## Current snapshot (2026-09-28)

- **Stage:** a synthetic-data preview on Render. Built: milestones 1–5 and 9, plus Timeline by account (Graph | List with money lines), compact Timeline/Overview controls and savings. Not started: AI insights (6; only the user's own API key), statements (7), the release/load gate (8). Status: [README](README.md).
- **Git:** local `feat/project-foundation` is ahead of GitHub. `main` and `origin/*` stay at `2d5dc6a` until the next push. The next push brings the compact UI, the Graph | List fixes, savings and demo data, the header Spending | Savings switch, and adds migration 0022 (`Account.is_savings`).
- **Last checks** (2026-09-28): 221 Django tests OK on SQLite; savings/flows 17/17 on Neon PostgreSQL; 12/12 Chrome checks; screenshots reviewed.
- **Local preview:** `tests/browser/server.py` on http://127.0.0.1:8000 (`browser-check`), with demo data from `tests/browser/seed_demo.py`. Details: [development guide](docs/development.md).
- **Owner actions (optional):**
  - in Render, Plaid keys: `PLAID_CLIENT_ID`, `PLAID_SECRET` and a newly generated `PLAID_TOKEN_KEY`
  - `TASKS_TOKEN` in Render, plus the GitHub secrets `TASKS_TOKEN` and `SITE_URL`
  - VAPID keys; an email provider; the Render cold-start decision
  - See the [operations guide](docs/operations.md).
- **Next:** push when the owner says so; then AI insights (brainstorm first; the provider is the user's choice).

Latest request (2026-09-28, with a sketch): switch Spending | Savings on both Overview and Timeline; drop the workspace name above the switch; put the switch beside the workspace selector; move Invite to the top right. Plan approved.
- **User choices:** the Timeline in Savings shows only savings accounts; the Overview hides By category in Savings; remove the Timeline's "‹ Personal" link too.
- **Built:**
  - one mode, in a `mode` cookie that the server reads; `timeline_scope()` and `reporting.saved_daily()`
  - the header: Invite (or Manage sharing) by the bell; the workspace selector as a popover dropdown with the switch beside it
  - Details: [development guide](docs/development.md#spending--savings-in-the-header-on-overview-and-timeline--september-28).
- **Verification:** 221 Django tests OK; 17/17 on Neon; 12/12 Chrome checks; screenshots reviewed.
- Committed locally, **not pushed**. The preview server is running with it.

## Log (newest first)

Latest request (2026-09-28): "now update all docs". Brought README (status, requested-features status, integrations), spec (status line, alerts row, Graph | List note), UX (old Budgets card, nav, Graph | List labels), development guide (how to open the local preview), plan (savings, renames) and operations (live service, Not yet done) up to date, and added this snapshot. Docs only; no product changes.

Latest request (2026-09-28): show savings and how much is in savings accounts; explain savings → checking → spending; give savings the same kinds of views as spending. Then: "seed the data for this browser-check account with accounts of all kinds, and transactions" ("can't see the savings button": it wasn't built yet). Plan approved.
- Answered: a transfer lowers savings but is never spending; spending rises only when the money is spent (no double counting).
- **Built:**
  - `Account.is_savings` (migration 0022; from the Plaid subtype, plus a Savings account switch on Edit)
  - `reporting.savings`; a Savings page (`workspaces/<id>/savings/`) and an Overview Savings card
  - chart tooltip labels via data attributes
  - `tests/browser/seed_demo.py` with made-up demo data. It has been run: 248 transactions in 8 Demo accounts in the preview database.
- Details: [development guide](docs/development.md#savings-page-and-demo-data--september-28).
- **Verification:** 220 Django tests OK; 16/16 on Neon; 12/12 Chrome checks; screenshots reviewed.
- Committed locally; **not pushed** (includes migration 0022). The preview server is running with the new code and data.
- Follow-up "instead of scrolling down to savings, make it toggleable between, savings and spending": the Overview top card now has a **Spending | Savings** switch (remembered per device; the Savings card below is removed). Charts are generalized to several per page. 220 Django tests and 12/12 Chrome checks OK; screenshots of both modes reviewed. Committed locally.
- Next: the owner reviews the preview, then says push; then AI insights (6).

Latest request (2026-09-28): make the frontend more compact.
- **Timeline:** Export CSV and Show money moving in a ⋯ menu at the top right; account tick boxes with Select all only inside Filters; filter fields side by side.
- **Overview:** a small switch turns the chart into a budget list (spent, left, over for the period shown).
- User choices: remove the separate Overview Budgets card; the Year view counts monthly budgets × 12.
- **Built:**
  - a native popover menu
  - a Filters disclosure button (no flash; open without JS)
  - a 2/4-column filter grid; accounts inside the form, with Select all / Clear all and a live count
  - the Overview Chart | Budgets switch, saved per device and applied before the page draws
  - `budget_progress(span=)` for the Year view, and totals that cover only the period shown
  - "Manage budgets" stays visible on Overview
- Details: [development guide](docs/development.md#compact-timeline-controls-and-the-overview-chart--budgets-switch--september-28).
- **Verification:** 215 Django tests OK; 11/11 Chrome checks; screenshots reviewed (phone filters, desktop menu, Overview Budgets light and dark).
- Committed locally; **not pushed**. No migrations.
- Note: the owner's editor selection shared a line of the local `.local/plaid.env` (the local token key) in chat. It was not repeated or used. Render should get a newly generated `PLAID_TOKEN_KEY`.
- Follow-up "how do i look at the ui before u push": started the local synthetic preview (`tests/browser/server.py`, http://127.0.0.1:8000, test login `browser-check`) for the owner to review. No product changes.
- Owner review of the local preview: the column header strip broke at each gutter (fixed: heads cover their gutter); lane rows drew over the bottom menu (fixed: nav `z-index: 40`, lanes isolated); the layout buttons are now **Graph | List**. Timeline specs 3/3 and 215 Django tests OK; screenshots checked. Committed locally, not pushed.
- Next: push when asked; then AI insights (6) with the user's own key.

Latest request (2026-09-28): "i need to import the fake plaid data so can u push that stuff as well to the website? i think u said its in a seperate branch right". Answered: no separate branch; all code is on `main` and deployed. The sandbox data lives only in the ignored local test database, and a synced bank can't be copied to the live site: its access token is tied to the local key, and bank data doesn't belong in Git. To get it on the live site, the owner adds `PLAID_CLIENT_ID`, `PLAID_SECRET` and a new `PLAID_TOKEN_KEY` in Render, then uses Settings → Connect a bank there (sandbox login `user_good` / `pass_good`). See the operations guide. No product changes; docs commits pushed.

Latest request (2026-09-28): AI insights must use only an API key each user enters, and update the docs. Also a per-account view: account tick boxes (none = total) and a second layout with one dated list per account, toggleable lines for money moving between them, scrolling sideways.
- Decisions (brainstorming, plan approved): account view first, then AI insights; on the Timeline page; lines only between the user's own accounts (transfers and card payments), with an 'elsewhere' stub.
- **Docs:** the AI key rule is recorded in the spec (credentials row plus data rules), plan milestone 6 and the README scope: no app, operator, pooled or fallback key; no key means no AI. Wireframe in UX 3b; rules in the spec section "Requested — 2026-09-28".
- **Built:**
  - `Transaction.money_in` (migration 0021 with a backfill)
  - account tick boxes on the Timeline
  - **Side by side** (`?view=lanes`): `budget/flows.py` pairs transfers (same amount, opposite direction, another visible account, at most 5 days apart); `components/lanes.html`; `assets/flows.ts` draws the SVG lines, with a toggle remembered on the device
  - manual Type now has Transfer out and Transfer in
- Details: [development guide](docs/development.md#timeline-by-account-tick-boxes-and-side-by-side--september-28).
- **Verification:**
  - 213 Django tests OK; flows, Timeline and import tests 27/27 on Neon PostgreSQL
  - 11/11 Chrome checks, including the new `lanes.spec.ts`; screenshots reviewed
  - Fixed along the way: a doubled mask on synced account names; `imports.spec.ts` searches for its own row
  - Real sandbox rows: 121 transfers and 0 pairs, as expected, because sandbox accounts have no matching counterpart rows
- Pushed on "push and push all changes to display on website" (2026-09-28): `main` fast-forwarded and both branches pushed. CI passed for `9f025d9`; Render then deploys and runs migration 0021 (the live site was not checked by the agent).
- Next: AI insights (6) with the user's own key only. Brainstorm first; the provider choice is the user's, since their key must match it.

Latest request (2026-09-28): "push. don't need reports. i like goals, make them optional, add recurring bills, and net worth." Pushed first (`bb77a20`). The user chose goals off until turned on, 3-day bill reminders, and net worth from synced balances plus manual items. Wireframes first (UX 6b), then three local commits:
- **Net worth:** Plaid cached balances each sync, plus manual items (home, loan); groups count only shared accounts.
- **Recurring:**
  - detected series to confirm or dismiss, or add your own
  - a 30-day forecast (an estimate, never spending)
  - reminders 3 days before, once per person/bill/date, generic push/email
  - `POST /tasks/daily/` with a bearer token, called by a free GitHub Action; it also runs a 6-hour catch-up bank sync
- **Goals:** a per-person Settings switch (default off, 404 when off); savings or debt with a linked balance or manual amount, plus the monthly amount needed.
- Found by the browser test and fixed: typed bill names were shortened like bank names ("Rent 2" → "Rent").
- Details: [development guide](docs/development.md#planning-tools-net-worth-recurring-bills-goals--september-28).
- Verification: 203 Django tests OK; 22/22 on Neon PostgreSQL; 10/10 Chrome checks; screenshots reviewed. Real sandbox: balances on all 14 accounts; the Bills page found monthly series in sandbox data.
- **Owner actions (optional, free):** `TASKS_TOKEN` in Render, plus `TASKS_TOKEN` and `SITE_URL` as GitHub Actions secrets ([operations guide](docs/operations.md#daily-task-bill-reminders-and-catch-up-sync-optional-free)).
- Pushed on "ok push" (2026-09-28): `main` fast-forwarded and both pushed. Render runs migrations 0018-0020 after CI; the Daily tasks workflow waits for its secrets (live site not checked by the agent).
- Next: the user picks among AI insights (6), statements (7) and the release gate (8).
- Follow-up question "did you update docs" (2026-09-28): yes. README, handoff, development, operations, plan, spec and wireframes are committed on the branch. `main` gets them on the next push (fast-forward). No product changes.

Latest request (2026-09-28): "do it" (Plaid slice 2). Built:
- signed-webhook automatic sync: ES256 JWT, 5-minute freshness, body hash; handled inside the request
- one sync at a time per connection, with `needs_sync` so an update arriving mid-sync isn't lost
- Reconnect (update-mode Link) for login-required errors
- a same-bank duplicate warning that unticks lookalike accounts
- new dependency `PyJWT` 2.15.0; migration 0017
- Details: [development guide](docs/development.md#plaid-slice-2-automatic-sync-reconnect-duplicate-warning--september-28).
- Verification: 184 Django tests OK; 25/25 on Neon PostgreSQL; 9/9 Chrome checks. Real sandbox: `reset_login` → `ITEM_LOGIN_REQUIRED` detected → update-mode link token issued.
- Real webhook delivery needs the live HTTPS site with the Plaid keys in Render (owner action).
- Pushed on "push" (2026-09-28): `main` fast-forwarded and both pushed; Render runs migration 0017 and installs PyJWT after CI (live site not checked by the agent).
- Next (user, 2026-09-28): no reports; optional goals, recurring bills, net worth. Wireframes first.

Latest request (2026-09-28): "ok i think i created a free plaid sandbox account". Plan approved; built Plaid slice 1 (in-request sync, because Render's free plan has no worker or cron):
- connect a bank (Link loads only on that page)
- the access token encrypted with `PLAID_TOKEN_KEY`
- choose accounts, each private
- sync after choosing and on Sync now (60 s cooldown; the cursor and changes commit together)
- pending→posted keeps edits; transfers, income and refunds from Plaid categories; Plaid category as a fallback behind rules and hand choices
- read-only synced rows; disconnect keeps history
- Also fixed: the email unsubscribe link is now deterministic (no timestamp).
- Details: [development guide](docs/development.md#plaid-sandbox-slice-1--september-28).
- Verification: 175 Django tests OK; 28/28 on Neon PostgreSQL; 9/9 Chrome checks.
- Real sandbox run done: 48 transactions synced, types and categories right, resync with no duplicates. Fixed history-ready timing.
- Owner clicked through Connect a bank by hand (automated Chrome stalls inside Plaid's consent screen): "Synced: 390 transactions". Checked: 390 unique rows, 2 years of history, no repeats.
- **Done by the owner:**
  - Plaid sandbox client_id and secret are in the ignored worktree `.local/plaid.env`. That file exists; a local `PLAID_TOKEN_KEY` is already generated there. Then the real sandbox run happens.
  - For the live site, add `PLAID_CLIENT_ID`, `PLAID_SECRET` and `PLAID_TOKEN_KEY` in Render ([operations guide](docs/operations.md#bank-sync-with-plaid-optional-sandbox-is-free)).
- Pushed on "psuh" (2026-09-28) together with email alerts: `main` fast-forwarded to `feat/project-foundation`, both pushed. Render runs migrations 0015-0016 and installs `plaid-python` after CI; the live site was not checked by the agent. Plaid stays off there until the owner adds the three Plaid keys in Render.
- Next: the real sandbox run; slice 2 (webhooks with signature checks, reconnect, duplicate warning); milestone 9.

Latest request (2026-09-28): "ok do email alerts, optional to turn on or off, defaulting to off, and with unsubscribe option".
- Built opt-in email alerts:
  - Settings → Notifications → Email alerts, off by default; needs a verified email
  - generic text, one email per person per evaluation
  - every email has a signed, no-sign-in unsubscribe link plus one-click `List-Unsubscribe` headers
- Push now also sends once per evaluation.
- Files: migration 0015 (`User.email_alerts`), `account_mail.py`, `notifications.py`, views/urls, `settings.html`, `email_unsubscribe.html`, `SITE_URL` setting.
- Details: [development guide](docs/development.md#email-alerts--september-28).
- Verification: 163 Django tests OK; 16/16 on Neon PostgreSQL; 9/9 Chrome checks; Settings screenshot reviewed.
- **Owner action:** production still uses the console mail backend, so emails go to the Render log. Pick a provider and set SMTP env vars ([operations guide](docs/operations.md#email-delivery-optional-the-provider-is-your-choice)).
- Pushed 2026-09-28 with the Plaid slice (see above).
- Next: milestone 9 (wireframes first) or the Plaid sandbox (needs the owner's free Plaid sandbox keys).

Latest request (2026-09-28): "i think this is a different branch right? can you make this one main? and then i thought you synced with plaid".
- Merged `feat/project-foundation` into `main`, so `main` now holds the whole app. The docs were already identical on both branches, and the merge was clean.
- `feat/project-foundation` was fast-forwarded to match. Work continues there in the worktree (its venv, node_modules and `.local/` stay there). Each push fast-forwards `main` and pushes both.
- `render.yaml` now says `branch: main`. **Owner check:** Render → budget → Settings → Branch should read `main`; change it there if the Blueprint didn't sync. Both branches are identical, so the live site is unaffected either way.
- The separate docs-sync step to root `main` is gone.
- Plaid: not built and not connected. It is milestone 3 and needs a Plaid account with sandbox keys (free) from the owner. Real bank data also needs production approval and has costs, and the release gates come first.
- Verification: pushed, remote heads checked. There were no code changes, so the tests were not rerun.

Latest request (2026-09-28): "look at the md files and continue with what is supposed to be next". The docs said CSV import, so it was planned and built (plan approved).
- Built: Account → Import CSV:
  - column mapping with an explicit sign, preview, all-or-nothing row errors
  - the same file imports once; duplicate rows are flagged one for one; undo
  - imported date, amount and description read-only; rules, budgets and alerts run after an import
- Also an app-wide select padding fix.
- Files: `budget/imports.py`, migration 0014, forms/views/urls, `import_preview.html`, `account.html`, `tests/browser/imports.spec.ts`.
- Details: [development guide](docs/development.md#csv-import--september-28).
- Verification: 157 Django tests OK; 28/28 on Neon PostgreSQL; 9/9 Chrome checks; screenshots reviewed.
- Pushed on "push it" (2026-09-28): feat `3e02623` and later, main `bc26200` and later. Render auto-deploys after CI and runs migration 0014; the live site was not checked by the agent.
- Next: email alerts (the user must choose a provider), milestone 9 (wireframes first), Plaid (milestone 3). Open owner actions are unchanged (VAPID keys, email provider, cold start).

Latest request (2026-09-28): "update all the docs if you haven't already".
- Fetched GitHub: nothing new since 2026-09-25 (no home-computer commits), and both checkouts are clean.
- Rewrote the README status by milestone; it still said "milestone 1 is in progress".
- Fixed one stale "not pushed" note (the visual theme was pushed later on 2026-09-25).
- Docs only; no code changed. Pushed on "ok push" (2026-09-28).
- Next: CSV import, or email alerts once the user picks a provider.

## Resuming on another computer (the user continues at home)

- Everything in Git is pushed to GitHub `kah-eru/budget`: the app code on branch `feat/project-foundation`, and the synced docs on `main`.
- To pick up on a new machine:
  1. Clone the repo. Create the worktree with `git worktree add .worktrees/project-foundation feat/project-foundation`, or just check out that branch.
  2. Follow the setup in [development guide](docs/development.md): venv, `pip install -r requirements.txt` (now includes `pywebpush`), `npm ci`, `npm run build`.
- **Not in Git, and it stays on the work computer:** the ignored `.local/` folder. That means `neon.env`/`neon-env.sh` (Neon dev credentials), `neon-site.env`, the synthetic browser/perf SQLite databases, and screenshots.
  - Tests and the browser checks run without them (SQLite plus `tests/browser/server.py`).
  - Only the Neon PostgreSQL runs need the credentials. Get them again from the Neon dashboard (project `dry-sea-53765016`) into a new ignored `.local/neon.env`. Never commit them or paste them into chat.
- The live site keeps running on Render; nothing there depends on this computer.
- Open owner actions: add VAPID keys in Render to switch on push ([operations guide](docs/operations.md#phone-push-optional-no-cost)); choose an email provider for email alerts; decide on the Render cold start (paid plan or keep-warm).

Latest request (2026-09-25, "ok continue on the list"): two local commits:
- `7a838a9` rule split templates: two-way, largest-remainder rounding; hand-made splits and manual categories win.
- `3d41b65` phone push: Settings toggle, push-only `/sw.js`, generic text, SSRF-checked endpoints, gone devices removed; new dependency `pywebpush`.
- Verification: 144 Django tests OK; 20/20 on Neon; 8/8 Chrome checks.
- Push delivery can't be tested in automated Chrome. **Owner action to enable push:** run `manage.py vapid_keys` and put both values in Render → Environment ([operations guide](docs/operations.md#phone-push-optional-no-cost)). No cost.
- Pushed 2026-09-25 on "update all docs and then commit and push"; Render auto-deploys after CI and runs migrations 0012-0013 (live site not checked by the agent). Push stays off on the live site until the owner adds the two VAPID keys.
- Next: email alerts (the user must choose a provider), CSV import, milestone 9 (wireframes first).

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

Latest request (2026-09-25, night): "Do the frontend first with these colors" (white + pink light; coffee bean + black cherry dark; more colours coming). Used `frontend-design` + `apple-design`. Built a token theme in `assets/app.css` (palette block -> roles -> Tailwind utilities), self-hosted Young Serif / Hanken Grotesk / Martian Mono, receipt-style spending summaries, OS-driven dark mode; templates moved off gray utilities. 78 Django tests OK, 5/5 Chrome checks, light/dark phone screenshots reviewed. Pushed later on 2026-09-25 with the next slice. Details: [development guide](docs/development.md#visual-theme--september-25-night). Next: CSV import/export, then Plaid sandbox (milestone 3).

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

Both branches are pushed to `origin` (GitHub `kah-eru/budget`) through the chart flash fix and this docs update (2026-09-25). Since 2026-09-28 Render deploys `main`, which is fast-forwarded to `feat/project-foundation` on each push. Earlier, each push to `feat/project-foundation` auto-deployed the Render preview after CI. Older handoff entries marked "not pushed" have since been pushed. No PR or merge. `main` carries the synchronized docs only; application code lives on `feat/project-foundation`. No pull request or merge exists. See [development guide](docs/development.md).

Execution ledger: `.superpowers/sdd/2026-09-22-budget-app/progress.md` (ignored). Python: worktree `.venv/Scripts/python.exe` (3.14.6); Node 22.23.1/npm 10.9.8.
