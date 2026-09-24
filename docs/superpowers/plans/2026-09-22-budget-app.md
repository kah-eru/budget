# Budget App Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` if the user selects delegated execution. Steps use checkbox syntax for tracking.

**Goal:** Deliver a private budgeting app with finance-sharing friends, bank sync, editable categorization, a spending timeline, AI insights, in-app/push alerts, and tested load scalability from the first release.

**Architecture:** One modular Django application with server-rendered pages and selected mounted React components, PostgreSQL, shared private object storage, and independently scalable web/operational/AI worker processes. Accounts belong to people; explicit account grants determine group visibility. Durable database jobs, sessions, leases, and quotas support multiple instances from the start. Manus is the separate operator SEO workflow for public pages.

**Tech Stack:** User-confirmed Django backend; Flowbite/Tailwind standard controls, Motion animation, Bklit UI charts, Kokonut UI selected interactions, and Manus.im for SEO tracking only. Proposed baseline: Python 3.12+, Django 5.2 LTS, PostgreSQL, official Plaid Python SDK, React/TypeScript components built into Django assets, and compatible Tailwind v4 packages. Use native browser APIs and maintained Web Push/cryptography libraries. The spending-insights AI provider is still unselected. Use k6 for the development-only load gate. Exact versions and component dependencies require verification at installation.

**Spec:** [Product and technical design](../specs/2026-09-22-budget-app-design.md).

**UX reference:** [Low-fidelity wireframes and user flows](../../ux-wireframes.md).

**Status:** Implementation started 2026-09-23 at the user's request, inline in the requested isolated worktree. Milestone 1 is partial; milestones 2-8 remain unstarted. Proposed files below are created only as needed. Current setup/evidence: [development guide](../../development.md).

### Current execution checkpoint

- [x] Django custom user, migrations, environment configuration, explicit DEBUG-only local SQLite mode and PostgreSQL deployment settings.
- [x] Personal/group workspaces, manual accounts, membership/grant records and central visible/editable-account queries.
- [x] Group creation, explicit sharing/revocation, member removal/leave and workspace switching; access tests exercised with synthetic users.
- [x] Framework sign-in/logout, database-backed Axes throttling/sessions, no-store/noindex responses, health/readiness.
- [x] Pinned local Flowbite/Tailwind/Motion build, React/TypeScript dependencies and Bklit/Kokonut registry configuration.
- [x] Fix browser referrer/CSRF and sharing account labels with observed failing regressions, then pass 27 Django checks and 2 Chrome browser tests; inspect phone/desktop screenshots.
- [x] Invitations with verified email, expiration/single-use/wrong-email tests, recovery and membership notices. On 2026-09-24, added separate mailbox proof before signup, verified-current-email recovery, and local console delivery; production delivery remains a deployment gate.
- [ ] PostgreSQL concurrency/two-process checks, shared private storage, full responsive navigation and actual mounted components.

This is not milestone 1 completion. Account-creation data-revision coverage is a deferred minor review finding; complete it before derived reports consume revisions.

## Global constraints

- Registration is invite-only; no public sign-up.
- USD only; flag and exclude unsupported currencies rather than silently converting.
- Store money as integer cents, preserving original bank fields separately from editable annotations.
- Private accounts and personal annotations never contribute to group output.
- Statements are owner-only in the first release.
- No real bank credentials, provider enrollment, paid upgrades, or deployment are part of the documentation task.
- Use Sandbox until financial correctness, access control, and operations checks pass.
- Keep one application and one database; add services only for measured needs.
- Finance-sharing invitations, the spending timeline, and read-only API-key AI insights are first-release features.
- AI uses the requesting user's key and separate account-owner consent for the selected workspace/provider; ordinary sharing never grants AI consent.
- Multiple web/worker processes must share sessions, leases, quotas, and file storage from the start.
- Phone-first layouts must reflow from 320 CSS pixels, use at least 44 by 44 CSS-pixel hit areas, preserve zoom, and keep controls usable with the keyboard open.
- Mobile performance targets: LCP <= 2.5 seconds, INP <= 200 ms, CLS <= 0.1; distinguish prelaunch lab measurements from field percentiles. Initial app-delivered JavaScript budget remains 150 KiB compressed, including loaded React, Flowbite, Motion, Bklit, Kokonut, and their dependencies. Measure deferred bytes separately; compatibility and budget compliance are unverified.
- Start with low-fidelity UX/user-flow review, then use Flowbite standard controls, Bklit charts, selected Kokonut interactions, and Motion transitions. Share a Tailwind theme; do not duplicate component behavior or let Flowbite mutate React-owned elements.
- Keep Django as the finance backend. Use Manus for public-page SEO only; private finance routes/data are excluded from indexing and SEO payloads. Live tracking awaits a public domain, selected pages, and connected SEO sources.
- Proposed load gate: 1,000 users, 1 million transactions, 100 concurrent sessions, 25 requests/second for 15 minutes; interactive p95 below 750 ms and p99 below 2 seconds.

## Review focus

1. A guessed ID or indirect total must not reveal private accounts; test in milestone 1 and repeat on each new entry point.
2. A sync retry or pending replacement must not duplicate spending or lose edits; test in milestone 3.
3. Transfers, refunds, and date boundaries must produce correct monthly/yearly totals; test in milestone 2.
4. Share revocation between alert creation and delivery must suppress access and delivery; test in milestone 5.
5. Browser installation/permission differences must not make the app unusable; verify on both actual phones in milestone 5.

Additional gates from the revised scope: timeline/report equality in milestone 2; AI consent/key/cost isolation in milestone 6; concurrent load and worker restart correctness in milestone 8.

## Proposed files

```text
manage.py
requirements.txt
package.json
package-lock.json
.env.example
.gitignore
config/
  settings.py
  urls.py
  wsgi.py
budget/
  models.py
  forms.py
  views.py
  urls.py
  permissions.py
  reporting.py
  timeline.py
  imports.py
  rules.py
  plaid.py
  jobs.py
  notifications.py
  statements.py
  insights.py
  ai_provider.py
  management/commands/run_jobs.py
  management/commands/seed_load_data.py
  migrations/
  templates/budget/
    components/
  static/budget/
assets/
  app.css
  app.tsx
  components/
    bklit/
    kokonutui/
  tests/
components.json
tsconfig.json
tests/load/budget.js
tests/browser/mobile.spec.js
```

Create files only when their milestone needs them. Framework-required package files are implicit. Reuse Django authentication/views/forms rather than building another authentication system. Server-side tests use Django's included runner; browser and load checks use the tools named in milestone 8.

## UX first: low-fidelity review

**Artifact:** [Wireframes and journeys](../../ux-wireframes.md), already drafted as documentation.

- [ ] Walk through first connection, private-to-shared account choice, inspect/edit purchase, create/backfill a category rule, budget alert, and consented AI analysis using the low-fidelity screens.
- [ ] Check that every screen has visible workspace context, a primary action, a clear Back/Cancel path, and loading/empty/error outcomes. Test understanding of past-history sharing and AI consent separately.
- [ ] Correct confusing navigation or missing steps in the wireframes before visual polish. Follow the Flowbite/Bklit/Kokonut/Motion mapping, choose the Kokonut Insights action component, and verify the same journey with reduced motion and failed enhancement loading.

## Milestone 1: private users, groups, and account sharing

**Files:** project configuration; `budget/models.py`, `permissions.py`, `forms.py`, `views.py`, `urls.py`; authentication/settings templates; `budget/tests/test_access.py`.

**Deliverable:** Partners and invited friends can log in, create/join finance-sharing groups, and explicitly share accounts while unrelated groups remain isolated.

- [ ] Initialize the Django project with PostgreSQL, environment-based configuration, migration support, built-in authentication, secure session defaults, and a custom user model established before the first migration.
- [ ] Configure database-backed sessions/shared throttling, shared private object storage, health/readiness checks, and bounded connection settings. Verify session continuity while alternating requests between two web processes; no in-memory ownership or lock state.
- [ ] Implement workspace/membership, invitation, account, and account-share records from the spec. Use one-time email verification for invitation acceptance; local development uses the console mail backend, and deployment uses a configured mail provider.
- [x] Write a failing access test covering personal/private, shared, unrelated-group, revoked-share, and removed-member cases. Assert both list exclusion and rejection of direct object access.
- [ ] Centralize visible-account and editable-account queries; require the authenticated user and active workspace on every operation. Account owner may edit their transactions; group members may edit shared budgets/rules only within their group.
- [ ] Build group creation, invite acceptance, explicit share/unshare, membership removal, and personal/group switching. Recheck access at mutation time; reject expired/reused/wrong-email invitations.
- [ ] Configure pinned compatible React/TypeScript, Tailwind v4, Flowbite, and Motion packages with a local asset build. Set up the documented Bklit/Kokonut registries and add only selected components and dependencies as their screens land. Scan Django templates and TSX for CSS utilities. Record installed versions and component licenses; use production assets, not a runtime CDN compiler.
- [ ] Mount selected React components inside dedicated Django-page containers; exclude them from Flowbite DOM initialization. Pass bounded authorized JSON safely, retain same-origin sessions and CSRF on mutations, and use one shared theme/runtime. Verify server-rendered financial values and fallback tables survive enhancement failure. Configure reduced motion before adding transitions.
- [ ] Compose the shell from Flowbite bottom navigation/sidebar, dropdown, badge, form, and alert components according to the wireframes. Use template includes for repeated markup, system typography, and restrained default styling. Preserve visible workspace context, safe areas, zoom, browser navigation, and private-cache rules; do not create custom equivalents of provided widgets.
- [ ] Test one user sharing different accounts in a partner group and a friend group, a friend contributing an account, and collaboration on shared budgets. Reject cross-group access; explicitly preview existing group history on invitation and preserve owner-only individual purchase edits.
- [ ] Add workspace data/permission revision updates for mutations, shares, and membership changes; use these for derived-output invalidation in later milestones.
- [ ] Add login throttling and password recovery using maintained framework-compatible mechanisms; do not hand-roll password handling.
- [ ] Run `python manage.py test budget.tests.test_access` and `python manage.py check`. Expected: access cases pass and the framework reports no configuration errors.

## Milestone 2: useful budgeting with manual imports

**Files:** transaction/category/annotation models and migrations; `reporting.py`, `timeline.py`, `imports.py`; dashboard/transaction/timeline/report templates; `budget/tests/test_reporting.py`, `test_timeline.py`, `test_imports.py`.

**Deliverable:** A user can import/edit purchases and inspect accurate personal/group reports and a chronological timeline before a bank connection exists.

- [ ] Add transaction source fields and workspace-specific annotations. Validate cents, USD currency, dates, and classification; preserve original data.
- [ ] Use this independent arithmetic fixture in reporting tests: $100 posted purchase + $20 posted purchase - $15 refund = $105 net spending; exclude a $100 card repayment and $200 internal transfer; display a $30 pending purchase separately. Expected cents are `10500` posted and `3000` pending.
- [ ] Add a Jan 31 / Feb 1 boundary case and an unrelated private-account purchase. Assert calendar reports place rows correctly and group totals omit the private row.
- [ ] Implement search, account/person/category/date filters, pagination, transaction editing, personal/group dashboard, yearly aggregation, and accessible empty states.
- [ ] Build the timeline feed with `(date, ID)` cursor pagination (50 default/100 maximum rows), a two-year interactive range cap, daily totals, zero-day filling, and a cumulative chart with an accessible table. Reuse reporting arithmetic; label income/transfers separately and keep pending estimates out of posted totals.
- [ ] Test $100 spend on day one, zero on day two, and a $15 refund on day three: daily cents `[10000, 0, -1500]`, cumulative `[10000, 10000, 8500]`. Test stable same-date ordering, permission filters, date boundaries, and cursor invalidation after a sync revision changes.
- [ ] Add initial account/date/ID and workspace/category indexes; cap pages, avoid per-row related queries, and aggregate in SQL. Add bounded-query-count assertions for 1 versus 100 rows; exports and large imports run in worker batches once milestone 3 supplies jobs.
- [ ] Implement CSV mapping/preview/commit. Reject malformed dates and sub-cent values, detect an identical file, and preview possible overlap without silently merging equal-looking purchases.
- [ ] Add tests for exact-file repeat, two valid identical-looking purchases, invalid-row all-or-nothing import, and export formula escaping. Verify personal notes never appear in a group export.
- [ ] Implement phone transaction rows, full-screen purchase editing, responsive filters, and tap/keyboard chart drilldown with equivalent tabular data. Preserve list position/filter URLs on Back, typed values on save failure, and visible actions when the virtual keyboard opens. Cancel stale filter requests.
- [ ] Reuse Flowbite timeline/list/table, forms, drawer/dialog, progress, and loading components. Add Bklit daily/cumulative/category charts backed by the same server-calculated data and equivalent HTML tables; use Motion for brief transitions. Check negative refunds, zero days, keyboard/touch selection, reduced motion, chart-load failure, and dependency/bundle cost. Do not add a second chart engine for these views.
- [ ] Run `python manage.py test budget.tests.test_reporting budget.tests.test_timeline budget.tests.test_imports`. Review phone/desktop screenshots and check 320/360/390/430/768/1024/1440 widths, keyboard use, chart-to-feed drilldown, and 200% text enlargement. Reuse this matrix for budgets, sharing, and Insights as they land.

## Milestone 3: Plaid sync and durable jobs

**Files:** `plaid.py`, `jobs.py`, `management/commands/run_jobs.py`; connection/job models; account templates; `budget/tests/test_sync.py`, `test_jobs.py`.

**Deliverable:** Sandbox accounts import automatically and through Sync now, with honest freshness/error indicators and safe retries.

- [ ] Add encrypted connection tokens, cursors, sync status, and leased jobs. Configure encryption keys separately from the database. Store no secrets in source or logs.
- [ ] Implement short database transactions for `SKIP LOCKED` job claims, shared per-Item leases, and bounded worker concurrency. Keep provider calls outside locks; separate operational and AI job pools. Atomically publish downstream evaluation work with committed source changes, then safely retry consumers.
- [ ] Write sync tests using synthetic provider responses: added/modified/removed records; pending replacement; duplicate job; a failure on page two; mutation-during-pagination; and an expired worker lease. Assert cursor/data atomicity and preservation of manual annotations.
- [ ] Implement Link token creation and public-token exchange for the authenticated owner. Use explicit imported-account selection; keep all accounts private initially.
- [ ] Implement paginated sync with provider-ID uniqueness and serialized work per Item. Stage full batches before committing the cursor and changes together.
- [ ] Verify webhook signatures/freshness before enqueueing. Test invalid signatures, duplicate valid delivery, and acknowledgement only after durable enqueue.
- [ ] Implement manual Refresh with the 60-second cooldown, coalescing, provider retry handling, and queued/waiting/success/reconnect/failure UI. Only owners refresh their Items.
- [ ] Add six-hour catch-up sync scheduling and durable post-sync budget evaluation. Retry transient failures with capped exponential backoff; surface persistent failures without discarding jobs.
- [ ] Wire large imports/exports and historical rule backfills to bounded jobs. Test two operational workers, lost lease recovery, overlapping manual/webhook jobs, and no partially published source batch. Advance data revisions when completed writes change timeline/report results.
- [ ] Run `python manage.py test budget.tests.test_sync budget.tests.test_jobs`. Exercise a Sandbox initial import, refresh, and reconnect scenario; verify the UI never reports a failed sync as successful.

## Milestone 4: custom categories, rules, and budgets

**Files:** `rules.py`, `reporting.py`; rule/budget/state models; category/rule/budget forms and templates; `budget/tests/test_rules.py`, `test_budgets.py`.

**Deliverable:** Users can create categories, preview/backfill name rules, and inspect monthly/yearly merchant/category budget progress.

- [ ] Write rule tests for case/whitespace normalization, missing merchant, empty pattern rejection, explicit priority, stable tie-break, manual override precedence, and workspace isolation.
- [ ] Implement exact-merchant and description-contains rules against bank source fields. Track annotation provenance; preserve manual edits on sync/backfill.
- [ ] Add matching-history previews and explicit backfill. Archive categories safely and disable rules targeting them; never delete referenced history.
- [ ] Add positive-dollar budgets targeting one category or one merchant/name match, with monthly/yearly period selection and no rollover.
- [ ] Test the boundary: a $100 budget with $100 posted spending is not exceeded; $100.01 is exceeded; pending spending does not trigger; refunds reduce current-period spending.
- [ ] Test baseline establishment after create/edit/join, recalculation after share changes, and no retroactive alerts for closed periods. Keep the baseline update and any event creation atomic under concurrent evaluations.
- [ ] Run `python manage.py test budget.tests.test_rules budget.tests.test_budgets`. Verify a Starbucks rule backfills only authorized history and leaves manual categories unchanged.

## Milestone 5: notification inbox and phone push

**Files:** `notifications.py`; notification/subscription/delivery models; notification/settings templates; `static/budget/manifest.webmanifest`, `static/budget/push.js`, service-worker source served at `/sw.js`; `budget/tests/test_notifications.py`.

**Deliverable:** A posted-spending crossing creates an inbox notification and an optional push on each subscribed device.

- [ ] Enforce one alert per recipient/budget/period in the database. Test duplicate evaluation, concurrent workers, refund/recrossing, month rollover, and device retry without duplicate inbox rows.
- [ ] Add unread/read inbox state and budget links. Recompute financial details from currently authorized records rather than storing stale amounts in notification text.
- [ ] Add device-specific push subscription/unsubscription and endpoint validation against SSRF. Request browser permission only on an explicit action.
- [ ] Use a maintained Web Push library and server-held VAPID keys. Persist per-device attempts, retry temporary failure, expire invalid subscriptions, and use a stable browser notification tag.
- [ ] Test member removal/share revocation after enqueue but before dispatch: no financial detail or unauthorized push can be sent. Test following an old notification URL after revocation.
- [ ] Cache public assets only. Test that logout/another user's login cannot recover financial pages from a service-worker cache.
- [ ] Run `python manage.py test budget.tests.test_notifications`; then verify actual push on both users' phones, installation guidance where required, denied permission, logout, and tapping an alert after session expiry.
- [ ] Verify browser and installed home-screen navigation, safe areas, offline/retry copy, and keyboard-open forms on iOS Safari and Android Chrome. Record actual versions; simulate bank-link return/cancellation and permission denial without losing page context.

## Milestone 6: consented AI insights with a user API key

**Files:** `insights.py`, `ai_provider.py`; configuration/consent/request/usage models; insights and key/consent forms/templates; `budget/tests/test_insights.py`, `test_ai_usage.py`.

**Deliverable:** A user can request a grounded spending analysis using their own key, with separate consent for shared data and bounded billable usage.

- [ ] Select one provider/model after checking its official API, structured-output capability, pricing, and retention controls. Record the selection and configured prices; no arbitrary endpoint field and no multiple-provider framework. Keep provider SDK calls in `ai_provider.py`; use a deterministic fake in tests.
- [ ] Add encrypted per-user keys, masked display, replace/remove, and account/workspace/provider AI consent controlled by the account owner. Test that group membership never permits borrowing another user's key or bypassing consent.
- [ ] Build minimized aggregate facts from the shared reporting calculation: dates, coverage, category/merchant totals, comparable-period differences, and budget progress with stable fact IDs. Exclude private/nonconsenting accounts, notes, descriptions, PDFs, identifiers, and transaction-level rows. Preview the payload and label partial coverage.
- [ ] Test unequal history windows, incomplete bank history, zero comparison spend, negative refund totals, mixed-consent group accounts, and malicious merchant/category labels. The same scope must produce the same monetary facts as the deterministic report.
- [ ] Implement one in-flight request per user, ten daily generations, a 200-row/8,000-input-token/1,500-output-token ceiling, a user-set daily dollar cap, and transactional cost reservation using current model pricing. Test concurrent requests cannot exceed reserved limits; block unknown pricing.
- [ ] Enqueue AI jobs in the separate pool; enforce timeout/response limits and authorize again before dispatch. No automatic call on sync/page load. Keep reservations for ambiguous timeouts and warn before a potentially duplicate charged retry.
- [ ] Validate structured output and fact IDs/numbers, sanitize text, and render monetary facts from app calculations. Test unsupported figures, malformed output, provider refusal, timeout, rate limiting, and no ledger writes/tool execution.
- [ ] Scope saved results by requester/workspace/provider/model/filters and data/consent/prompt revisions. Recheck access on completion/read; invalidate on revocation or source changes, purge on key removal, and expire text after 30 days. Test revocation while inference is in flight.
- [ ] Integrate the selected Kokonut UI component for the request/status action with Motion feedback. Preserve the existing Generate insights workflow, confirmed status, keyboard focus, loading/error text, and reduced-motion behavior; no chat or automatic paid generation is implied by component reuse.
- [ ] Run `python manage.py test budget.tests.test_insights budget.tests.test_ai_usage`. Verify the app remains fully usable with no key, denied consent, or a failed provider. Real-data/billable calls are a separate user action through configured settings.

## Milestone 7: statements and private deployment setup

**Files:** `statements.py`, statement models/forms/templates; `budget/tests/test_statements.py`; deployment configuration and `docs/operations.md` created for the selected host.

**Deliverable:** Owner-only statement access, tested data recovery, and a deployment ready for the two users' real accounts.

- [ ] Add optional Plaid Statements access for supported accounts without blocking Transactions linking. Test an institution that does not support Statements and one that requires additional access.
- [ ] Implement owner-only PDF upload/download with the 10 MiB limit, content checks, randomized private storage, and safe attachment headers. Reject non-PDF and oversized content.
- [ ] Test that a group member cannot list or download PDFs for an otherwise shared account, and that direct storage URLs are inaccessible.
- [ ] Provide printable app reports clearly distinguished from official statements. Complete CSV import/export and account data export before exposing deletion.
- [ ] Implement disconnect, retained-history choice, and confirmed deletion. Test provider revocation failure is surfaced/retried and that deleted accounts cannot be revived by delayed jobs/webhooks.
- [ ] Choose the host and domain with an explicit cost review. Configure HTTPS, secrets, independently scalable web/operational/AI workers, shared private object storage, transactional email, redacted logs, and daily encrypted backups. Verify a second replica uses the same sessions/permissions/files without application changes.
- [ ] Document deployment/update/rollback, key rotation, worker recovery, reconnect support, provider costs, data deletion, and a restore rehearsal including reapplication of deletion/revocation records.
- [ ] Prepare the public/private indexing boundary: authenticate private finance routes, add noindex directives, and omit them from sitemaps and SEO payloads. Check representative purchase, statement, invitation, and settings routes. Robots rules must never substitute for authorization.
- [ ] When the public domain/pages and SEO sources are available, configure Manus SEO tracking for those pages only. Record connected sources, baseline audit, reporting window, keyword/indexing metrics and available organic traffic data in operations docs. Start with manual reports and distinguish missing data from zero and SEO scores from actual rankings. Verify payloads contain no financial/session/invitation data. If no public surface exists, record live tracking as pending; do not claim it is connected. Built-in Manus-hosted SEO is not assumed to be an embeddable Django integration.
- [ ] Run `python manage.py test`, `python manage.py check --deploy`, and `python manage.py makemigrations --check --dry-run`; resolve failures and relevant deployment warnings. Restore a backup into an isolated environment and verify access and totals before production use.
- [ ] Verify current Trial eligibility and institution coverage, especially Marcus and statement support. Real linking happens through each user's own Plaid flow; do not request passwords in chat. Track consumed Item capacity before inviting additional users.

## Milestone 8: scalability and concurrency release gate

**Files:** `budget/management/commands/seed_load_data.py`, `tests/load/budget.js`, `tests/browser/mobile.spec.js`, `budget/tests/test_concurrency.py`, and `docs/operations.md` with measured results.

**Deliverable:** Recorded evidence that the first release meets its proposed capacity target and preserves access/accounting correctness across multiple processes.

- [ ] Add a synthetic-data seeder guarded against production databases: 1,000 users, multiple overlapping/isolated groups, one million transactions over two years, and one 100,000-transaction workspace. Use a fixed random seed and record hardware and indexes; never use real credentials/data.
- [ ] Add a k6 scenario running 100 authenticated sessions at 25 requests/second for 15 minutes after warm-up, mixing dashboard (30%), timeline pages (40%), filtered/yearly reports (20%), and authorized small edits/job enqueue (10%). Keep provider calls mocked and record per-route metrics. Fail on dropped iterations as well as route latency/error thresholds so insufficient load generation cannot appear to pass.
- [ ] Set thresholds to per-route p95 under 750 ms/p99 under 2 seconds and unexpected HTTP failures below 1%. Record actual throughput, database connection peak, memory, query counts, and CPU; inspect slow-query plans before adding caches.
- [ ] While the interactive scenario runs, enqueue 10 synthetic operational jobs/second with 20-100 ms mocked provider latency and measure operational queue start p95 under 30 seconds. Separately hold an AI mock call for 30 seconds and verify the interactive/operational targets still hold; record pool sizes so the result is reproducible.
- [ ] Run two web replicas and at least two operational workers. Restart one replica and terminate a worker mid-job; assert session continuity, lease recovery, one committed purchase, preservation of edits, and correct cost reservations. Test simultaneous sharing revocation and timeline/AI/notification requests with zero unauthorized output after revocation commits.
- [ ] Verify graceful shutdown, readiness, bounded database pools, and backward-compatible migrations. Confirm each worker pool's configured concurrency stays within provider/database budgets when replicas are added.
- [ ] Add Playwright browser checks for mobile navigation, viewport overflow, long transaction names/large amounts, purchase edit success/failure, filter Back navigation, sharing dialogs, and AI loading/error states. Use synthetic data; verify Chromium, Firefox, and WebKit, then run the actual-device Safari/Chrome checks in the spec. Review screenshots rather than treating screenshot generation as review.
- [ ] Run `npx playwright test tests/browser/mobile.spec.js` after configuring the development-only browser runner. Record viewport/browser/device versions and manual VoiceOver/TalkBack, keyboard-open, safe-area, and text-zoom results. Automated WebKit coverage does not establish iOS device compatibility by itself.
- [ ] Measure useful first render, key interaction latency, layout shift, and compressed app-delivered JavaScript including loaded React, Flowbite, Motion, Bklit, Kokonut, and transitive dependencies under a documented mid-range Android/4G profile. Check spec section 7 targets; report initial/deferred bytes and avoid duplicate runtimes. Exercise reduced motion, fallback content, and React/Flowbite ownership boundaries. Record lab evidence separately from field metrics and server load-test results.
- [ ] Run `python manage.py test budget.tests.test_concurrency`, followed by `k6 run tests/load/budget.js` against the isolated test deployment configured in the harness. Save the command, environment/hardware, dataset, results, and bottleneck fixes in operations docs. These commands are planned, not run in this documentation task.
- [ ] Resolve failures before marking scalability verified; any revised target must be recorded explicitly. Rerun focused correctness tests for any performance change, then the release checks from milestone 7.

## Delivery and expansion gates

Milestones 1-2 yield collaborative finance sharing, CSV data, and the spending timeline. Milestones 3-5 add sync, rules, and notifications. Milestone 6 adds requested AI insights. Milestone 7 supplies statements and deployment setup; milestone 8 verifies concurrent-load readiness. All eight are first-release scope; interim milestones do not count as the full requested app.

Before connecting real accounts for partners or friends, pass the multi-group isolation and multi-instance checks and review remaining Plaid capacity. Friends can share finances in the first release. Multiple-worker correctness is a release requirement, not a future redesign. Paid Plaid, additional hosting capacity, public signup, and native apps remain separate operational/product decisions.

Every confirmed feature still maps to a milestone. The execution checkpoint records actual implementation; unchecked full-release tasks remain pending. Continue milestone 1 inline from the handoff. No production readiness, financial calculations or measured scalability is claimed.
