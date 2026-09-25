# Budget app: product and technical design

Date: 2026-09-22

Updated: 2026-09-23 for Motion, Bklit UI, Kokonut UI, and Manus SEO direction.

Status: implementation authorized on 2026-09-23; milestone 1 foundation is in progress. This document defines the full intended release, not a claim that every feature exists.

## Implementation snapshot — 2026-09-24

Implemented locally: custom Django user, personal/group workspaces, memberships, owned manual accounts, account grants, centralized access queries, explicit share/unshare, member removal/leave, database-backed sign-in throttling/sessions, private response headers, health/readiness endpoints, and a low-fidelity server-rendered shell.

Manual accounts belong directly to users; bank-connection metadata will be added in milestone 3. Group ownership is stored on Workspace, with Membership rows for additional members. Personal access is owner-only even if an erroneous membership row exists. Sharing/removal services lock the workspace before rechecking permissions; PostgreSQL tests with separate database sessions confirm this (`budget/tests/test_concurrency.py`).

PostgreSQL is the deployment configuration. SQLite is an explicit DEBUG-only synthetic-data fallback, not a scalability substitute. Flowbite/Tailwind and Motion assets build locally; React is mounted only for the Timeline's Bklit running-total chart, lazily loaded, with the daily table as its accessible equivalent. Kokonut components and further chart accessibility checks remain pending.

Invitations now use seven-day single-use hashed tokens, owner-only issuance/revocation, and explicit history disclosure. New users must open a separate one-hour email setup link before their identity is created; existing users must verify their current email before joining. Joining shares none of the new member's accounts. A standalone invitation (issued from the inviter's personal workspace) only creates a private login; it grants no group or account access. Signed-in users can change their password from More. Affected account owners receive a group-page membership notice. Removal also revokes pending invitations for that email. Django password recovery is restricted to verified current email addresses. Local email uses the console; real delivery is not configured or verified.

Manual transactions (integer cents, USD, expense/refund/income/transfer, pending) month/year spending summaries with a per-month year table, a searchable/filterable timeline (daily and cumulative totals table, day-grouped feed, revision-checked cursor paging), and per-workspace annotations (display name, classification override, note; no category yet) exist; imports and timeline charts do not. Budgets, banks, jobs, AI, statements, deployment and live Manus SEO are not implemented. Row-locking checks pass on hosted PostgreSQL (Neon, synthetic data); load and multi-instance deployment remain unverified. Current evidence and known issues are in [development setup and verification](../../development.md).

Working name: Budget app.

## 1. Purpose and confirmed requirements

Build a budgeting app initially used by the user and their girlfriend in the USA. Each person controls which financial accounts they share with a partner or invited friends. Friends are finance-sharing collaborators, not merely future independent users. Invitations, shared budgets, and personal/group views belong in the first release. Keep the deployment small while designing and verifying code and load scalability from the start.

Confirmed features:

- Monthly and yearly spending views.
- Automatic transaction integration and a manual sync button.
- Editable purchase details, custom categories, and rules that apply to past, current, and future transactions by name.
- Merchant/category spending thresholds and both in-app and push notifications.
- Statements.
- Selective account sharing, rather than automatically exposing all accounts to a partner.
- Invite friends to collaborate on shared finances from the first release.
- Scalable code structure and concurrent-load handling from the first release.
- API-key-based AI financial insights. The user has no provider preference.
- A chronological timeline of money spent.
- A polished phone-first web app with responsive layouts and fast interactions, while remaining fully usable on tablets and desktop.
- Use Flowbite/Tailwind standard controls alongside Motion (motion.dev), Bklit UI, and Kokonut UI. Start design with low-fidelity wireframes focused on UX and user flow.
- Keep Django as the backend; use Manus.im for SEO tracking only, as explicitly clarified on 2026-09-23.

Added by the user on 2026-09-25 (requested; not implemented). Section 3, "Requested additions — 2026-09-25", has the first design defaults:

- Bank sync that includes loan accounts, with manual entry kept as a backup.
- Automatic sorting into standard groups (groceries, utilities, ...), and splitting one transaction across several categories, including by rule.
- A budgeting framework that separates fixed bills, irregular/annual costs and flexible daily spending, and shows true disposable income.
- Visual reports: color-coded category charts, pie/donut breakdowns and trend graphs.
- Goal tracking: emergency fund, debt payoff, vacation, large purchase.
- Customizable alerts by push or email: approaching a limit, upcoming bill due dates, unusual account activity.
- Recurring transaction projection (rent, mortgage, subscriptions) and a cash-flow forecast.
- Net worth and investment monitoring: assets, liabilities and portfolios in one dashboard.
- Multi-device access (web plus iOS/Android) and collaborative sharing for couples and families. The existing design already covers both.

The user wants spending visibility and notifications, not the ability to decline card purchases.

Known institutions: Wells Fargo, Marcus savings, Chase checking and credit, and Chime. The girlfriend's institutions and both users' phone platforms have not been supplied; neither blocks this design.

## 2. Proposed defaults

These fill gaps in the conversation and can be changed during review.

| Decision | First-version default |
| --- | --- |
| Platform | Phone-first responsive web app, usable in a browser and installable on a phone home screen; mobile interaction quality is a first-release requirement. |
| Registration | Invite-only; no public sign-up. |
| Views | Personal workspace plus explicitly joined group workspaces. |
| Sharing | Account owner shares individual accounts with a group; all group members see those accounts' available transaction history. |
| Group edits | Members manage shared budgets/categories/rules; only an account owner edits individual purchases from that account. |
| Private annotations | Personal notes and category overrides are not copied into group views. |
| Currency | USD only; flag and exclude unsupported currencies rather than silently converting. |
| Time | Calendar months/years; workspace timezone initially America/Denver and editable. |
| Budget thresholds | One positive dollar limit per budget per month or year; no rollover initially. |
| Alert basis | Posted net spending strictly greater than the limit; pending shown separately. |
| Push privacy | Generic lock-screen text; detailed amounts visible after opening the authenticated app. |
| Expenses split across categories | Requested by the user on 2026-09-25. Categories ship first with one category per purchase; splits follow (see Requested additions). |
| Friends | Invite into an existing finance group or create a separate group with that person; explicit account sharing determines visibility. |
| Timeline | Dated purchase feed plus daily net spending and a cumulative spending chart for the selected period. |
| AI activation | Optional, off until a user adds a key and consents; request-driven insights rather than unattended periodic charges. |
| AI credentials | Each requesting user supplies their own provider key; group membership never grants use of another member's key. |
| AI provider | No user preference; choose one supported provider/model at implementation, not an arbitrary-endpoint or multi-provider framework. |
| Capacity target | Proposed first-release benchmark: 1,000 registered users, 100 concurrent sessions, 1 million transactions. These are test targets, not measured claims. |

## 3. Small first release

### Accounts and sharing

Every bank connection has one application owner. Connecting a bank never shares anything automatically. After connection, list the accounts returned by the bank and let the owner choose which to import and which to share with each group. Newly discovered accounts remain private until explicitly shared.

The same user can share selected accounts with a partner in one group and different accounts with friends in another. A one-to-one friendship uses a two-person finance group; there is no separate social graph. Friends can view shared spending/timelines and manage that group's budgets, categories, and rules under the same permissions as any other member. They cannot modify bank connections or access unshared accounts. Payments and expense settlement are outside this feature.

A group owner creates a group and can issue an expiring, single-use invitation bound to an intended email address. Use a seven-day expiry and store a hash of the random token. Joining requires authentication and verified control of the intended email address. Group membership grants access only to accounts already shared with that group. Adding a member shows a warning that the new member will see the group's existing shared history; account owners receive an in-app membership notice and can revoke their shares.

Sharing includes transaction dates, amounts, bank merchant/description, account label, and group-specific annotations. It does not include credentials, connection tokens, private annotations, or statement PDFs. PDFs remain owner-only in the first release because they may contain other accounts and sensitive identifiers. Sharing confirmation explicitly says that past and future transactions will become visible.

Revocation immediately removes the account from group queries, totals, exports, and future notifications. Previously downloaded exports or delivered notifications cannot be recalled. Account owners can revoke sharing; members can leave groups; group owners can remove members. Leaving/removal also revokes that member's account shares to the group. An owner must transfer ownership or delete the group before leaving.

Avoid duplicate connections for a joint bank account: link once and share it. Detect likely overlaps using institution/account metadata, warn for review, and never merge accounts solely because their last four digits match.

### Dashboard and transactions

Choose a personal or group workspace, then a month or year. Show posted spending, income, pending spending, budget progress, and last successful sync. Filter by account, merchant, category, and account owner. Group totals cover only accounts shared with that group, never private accounts owned by its members.

Transaction detail permits display-name, category, note, and classification overrides in the active workspace. Editable classification is expense, income, refund, or transfer. Preserve the bank's original amount/date/description; user changes do not modify the bank record. Do not offer arbitrary editing of imported amounts in this first release.

Transfers between the user's accounts and credit-card repayments are excluded from spending and income totals. Merchant purchases count once. Bank-provided classification is a starting suggestion; permit correction and expose uncertain cases instead of pairing transactions by amount alone. Refunds reduce spending in their posted period and assigned category; do not silently rewrite the original purchase's period.

Use integer cents for USD amounts, with exact decimal conversion at import. Validate positive budget limits and reject sub-cent input. Keep source date-only transaction dates as dates, not UTC timestamps; use the workspace timezone for selecting the current reporting period.

### Spending timeline

Provide a chronological feed grouped by transaction date with merchant, amount, category, account owner, and pending/posted status. Default newest-first with a stable `(date, transaction ID)` cursor, 50 rows per page, and a maximum of 100. Fetch another page on demand; never download all history to the browser. Do not invent times of day when the bank supplies only a date. Pending-to-posted replacement updates the same logical purchase rather than creating two spending events.

Above the feed, show daily net spending and a cumulative chart across the selected month, year, or custom range. Use the same filters and reporting calculation as the dashboard. Fill missing days with zero; refunds may make a daily total negative and reduce the cumulative line. Keep pending estimates separate. Income and transfers can be shown as labeled feed entries when requested, but never increase spending totals. Cap interactive custom ranges at two years; older history remains accessible by changing the range or through a background export.

Selecting a date or chart point filters the transaction feed to its contributing rows. Provide the chart values in a keyboard-accessible table as well. Show data freshness and refresh results after sync, edits, rule application, or access changes. A concurrent sync can alter the result set; invalidate the current cursor and offer Refresh when its workspace data revision changes rather than silently skipping/duplicating rows.

### AI financial insights

Add an Insights page where a user chooses a workspace and date range, previews what will be sent, and requests an analysis using their configured API key. Initial insights explain spending changes, top categories/merchants, budget progress, and unusual increases relative to a comparable period. Examples: where spending increased this month, which shared category is closest to its budget, or how daily spending has changed. These are read-only explanations, not autonomous money movement, bank actions, or investment recommendations.

The app computes totals, percentages, comparison periods, and budget progress deterministically. AI receives a bounded structured summary with fact IDs, period boundaries, coverage/freshness indicators, and only necessary category/merchant totals. Default monthly comparisons use equal elapsed-day windows; mark incomplete history and never present unavailable history as zero. Predictions, if later added, must be separately labeled estimates. AI output is not the accounting source of truth.

Data and permission rules:

- Store each user's API key encrypted server-side; show only a masked identifier. Support replace/remove; never put keys in prompts, logs, browser storage, group settings, or exports. A user cannot spend another member's key by changing a request ID.
- Viewing shared finances is not consent to send them to an external AI service. Each account owner separately opts in that account for AI analysis in that workspace and for the selected provider. Provider changes require fresh consent. Exclude accounts without consent and clearly label the analysis as partial; ordinary dashboard/timeline totals still include all visible accounts.
- Category/merchant labels can also be sensitive. Preview the actual minimized payload; omit names of people, account numbers, account labels, credentials, notes, raw descriptions, individual purchases, and PDFs. Use aggregate counts and totals. Treat all labels as untrusted data, never as instructions.
- Scope every request, queued job, result, and cache entry to the requesting user, workspace, selected provider/model, filters, permission/consent revision, data revision, and prompt version. Recheck access and consent immediately before dispatch, after completion, and on result access. Invalidate results after relevant revocation; do not expose stale summaries to former group members. Already dispatched data cannot be recalled from a provider; explain this when granting consent.
- Results are private to the requesting user even when analyzing a shared group. Automatically sharing AI reports or using a pooled group key is deferred.

Execution and cost rules:

- Run inference in a background job, never in the dashboard request. No AI call is made just by opening the app or syncing a bank. The core app stays usable without a key or during provider failure.
- Proposed limits: one in-flight request per user, ten generations per user per day, at most 200 aggregate rows, 8,000 input tokens, and 1,500 output tokens per request. Disclose truncation/Other aggregation and the covered population; apply limits before dispatch using the selected model's supported accounting.
- Show provider/model, billable-use notice, estimated cost, and returned usage when available. Require a user-set daily dollar ceiling before enabling requests. Atomically reserve a conservative maximum charge using current configured model pricing and limits, then reconcile actual usage. Block if pricing is unknown, the daily ceiling would be exceeded, or ambiguous previous requests have exhausted the remaining reservation. This bounds app-issued requests, not other use of the same key or a provider's entire invoice.
- Configure an allowlisted provider URL/model server-side. No arbitrary API base URLs from users. Limit provider concurrency independently of sync/push, enforce timeouts and response-size limits, and reject unknown model IDs.
- A network timeout after dispatch may still be billable. Do not blindly retry ambiguous generations; retain the reservation and show a retry warning. Reuse a successful result only when its scope and data/consent revisions still match.
- Require structured output with known fact references. Render amounts from the app's facts, validate referenced IDs and any numeric claims, and reject unsupported figures. Sanitize output; disable model tool execution and external URL fetching. Malformed output, instruction-like merchant labels, and unavailable data produce a safe error or clearly bounded summary, never changed ledger data.
- Record status, latency, usage, cost estimate, and redacted error metadata. Default retention is 30 days for generated text; delete/expire stored payloads promptly, and purge relevant results on key removal or access revocation. Before enabling real-data AI, review the chosen provider's retention controls and terms; do not promise zero retention without verification.

One concrete provider integration is enough initially. Keep the call in a focused module so a second provider can be added when requested, while leaving the financial aggregation and permissions independent of the model SDK.

### Categories and rules

Categories and rules belong to one workspace. Example: description contains `STARBUCKS` -> category `Coffee`; a separate Coffee budget has a $60 monthly limit.

Support exact merchant matching or description-contains matching. Trim, collapse whitespace, and compare with Unicode case folding. Preserve the original text. Reject empty patterns. No regular expressions or AI categorization are needed initially.

Precedence: manual workspace override, then first matching enabled rule in explicit priority order, then mapped bank category, then Uncategorized. Resolve equal priorities by stable rule ID. Match original bank fields, not edited display names. Archiving a category preserves history and disables rules that target it; offer reassignment instead of deleting referenced categories.

Saving or changing a rule offers a preview of matching imported transactions and a checkbox to apply it to existing history. That operation preserves explicit manual overrides. New and bank-modified transactions use the current rules automatically. Disabling a rule stops future application; historical changes require a separate previewed reapplication. Historical coverage is limited to data actually imported.

### Budgets and notifications

A budget belongs to one workspace and targets either a category or a merchant/name match. Group budgets use all accounts shared to that group; personal budgets use the owner's imported accounts. Show spent, remaining, and overage, including negative net spending if refunds exceed purchases. Pending amounts appear as a separate estimate and do not trigger alerts.

Evaluate active-period budgets after completed syncs, CSV imports, purchase edits, rule backfills, and sharing changes. On budget creation or editing, show current status and establish a baseline without issuing an immediate alert. New group members establish their own baseline and do not receive past threshold events.

When posted net spending moves from at-or-below to above the limit, create one in-app alert per recipient, budget, and period. A refund followed by another crossing does not send a second alert in that period. Editing a budget does not reset its sent-alert record. A new month/year starts a new period. Backfilling closed periods updates reports without sending old alerts.

In-app alerts have unread/read state and open the affected budget. Personal alerts go only to the owner; group alerts go to current group members. Recheck membership and sharing on display, opening, and immediately before push dispatch; obsolete alerts show no stored financial detail. Recompute detail from authorized data.

Each user explicitly enables push on each device. Use generic push text such as `A budget needs your attention` and an opaque notification link. Use one in-app record plus a delivery record per device; retries do not create extra inbox alerts. Push delivery is best-effort and cannot guarantee exactly-once display. Use a stable notification tag to reduce visible duplicates, retry temporary failures, and remove expired subscriptions. In-app alerts work if push is unavailable or denied.

On iPhone/iPad, the proposed web app requires home-screen installation and iOS/iPadOS 16.4+ for Web Push. Request permission only after the user taps Enable notifications. Verify both actual devices before release. [WebKit platform guidance](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)

### Statements and imports

Provide original bank PDFs where available, owner-only PDF uploads, and printable spending reports clearly labeled as app reports. A generated spending report is not an official bank statement. Do not parse uploaded PDFs in the initial version.

CSV import supports date, description, amount, and optional category, with a mapping/preview step and an explicit sign convention. Import into an owned account only. Record a file hash and source row number to make exact-file reimport idempotent; overlapping files and Plaid overlap require candidate review rather than deleting legitimate same-day/same-amount purchases. Reject invalid rows with row-specific messages before committing the batch. Escape formula-leading cells in CSV exports.

PDF uploads have a 10 MiB limit, PDF content checks, randomized storage keys, and authenticated attachment downloads. Store outside public static/media paths. Do not publish permanent public PDF URLs.

### Requested additions — 2026-09-25

User-requested features with proposed first defaults. None are implemented. "Covered" means the existing design already includes it.

| Feature | Status | Proposed first default |
| --- | --- | --- |
| Automatic bank syncing, including loans; manual entry as backup | Covered, plus loans added | Plaid Transactions for checking, savings and credit. Loan balances and payment details need Plaid Liabilities, a separate product whose Trial availability and cost are unverified; check before enabling and get the user's approval for any cost. Syncing is not real time: banks refresh one to four times a day (section 4). Manual accounts and transactions exist today. |
| Standard categories and custom rules | Covered | A seeded set of standard categories (groceries, utilities, dining, transport, housing, ...), editable per workspace. The bank's category is a starting suggestion (precedence in Categories and rules). |
| Split one transaction across categories | New | A split divides a transaction's amount into category lines that sum exactly to it in integer cents, as a per-workspace overlay; the bank record is unchanged. A rule may apply a split template (for example 70% Groceries / 30% Household). Percentages round by largest remainder so the lines always add up exactly. Budgets and reports count each line in its category. |
| Budget framework: fixed, irregular/annual, flexible | New | Each budget has a kind. **Fixed** bills have an expected amount and due day. **Irregular** costs have a yearly amount shown as a monthly set-aside (yearly ÷ 12), and the set-aside accumulates toward the bill. **Flexible** spending has a period limit. Disposable income = expected monthly income (user-entered, or the average posted income over the last three complete months) − fixed bills − irregular set-asides. Flexible budgets are compared against what remains. Estimates are labeled as estimates. |
| Visual reports and analytics | Partial (the Timeline running-total chart exists) | Category donut/pie for a period, a monthly trend by category, and budget progress, all with Bklit. Category colors come from theme tokens and are never the only cue: labels and values appear too, and every chart has an equivalent table. |
| Goal tracking | New | A goal has a name, target amount, optional target date and a kind (savings or debt payoff). Progress comes from a linked account balance where available (savings, or a loan/credit balance for payoff) or from manual contributions. The required monthly amount to hit the date is computed deterministically. A goal belongs to one workspace; group goals use only shared accounts. |
| Customizable alerts: approaching a limit, bills due, unusual activity; push or email | Partial (budget crossing, in-app and push) | Per-budget thresholds (default 80% and 100% of the limit; each threshold alerts once per period). Bill-due reminders a user-chosen number of days before a fixed bill or confirmed recurring charge. Unusual activity is a deterministic rule, not AI: a transaction over 3× that merchant's median, or a first-seen merchant above a user-set amount. Email is an opt-in channel per user with generic text and a sign-in link, like push. It needs an email provider, which isn't configured; choosing one is the user's decision. |
| Recurring transaction projection and cash-flow forecast | New | Detect candidate series (same merchant, amount within ±10%, a regular weekly, monthly or yearly interval, at least three occurrences). The user confirms or dismisses each; manual entries are allowed. Confirmed items project forward into a labeled forecast (expected income − upcoming bills) and never count as spending until posted. |
| Net worth and investment monitoring | New (was deferred) | Net worth = assets (account balances, investment holdings value, manual assets such as a home or car) − liabilities (credit cards, loans). Balances, holdings and loans need Plaid Balance, Investments and Liabilities, whose availability and cost are unverified; manual values are the fallback. Read-only: no trading and no investment advice. Accounts stay private until shared, and a group net worth covers only shared accounts. |
| Multi-device access | Covered | Data lives on the server, so every browser sees the same state. As of 2026-09-25 the web app is installable to iOS and Android home screens. Native apps are reconsidered only for a concrete missing capability (section 8). |
| Collaborative sharing for couples and families | Covered | Separate logins, groups, per-account sharing, joint accounts linked once and shared, and shared budgets (Accounts and sharing). |

Permission rules from the rest of this document apply to every addition: workspace-scoped data, owner-only account edits, private accounts excluded from group totals, and permission rechecks before any alert is delivered.

## 4. Plaid feasibility and integration

Facts checked on 2026-09-22; recheck the account agreement and coverage before connecting real accounts.

The current US/Canada Trial supports ten lifetime-created Production Items and includes Transactions, Transactions Refresh, and Statements. Removing an Item does not restore capacity. Calls on existing Items have no overall Trial usage cap, but endpoint rate limits still apply. Sandbox uses synthetic data. These are provider terms, not a promise of permanent free service. Hosting/storage remain separate costs. [Trial details](https://support.plaid.com/hc/en-us/articles/39994173227159-What-is-the-Plaid-Trial-plan)

The user's institutions likely need four Items if Chase checking and credit share a login. This is an estimate, not a verified connection count. Wells Fargo and Chase are listed for Trial OAuth access. Chime has a documented OAuth integration. Marcus has historical Plaid support, but current product coverage must be verified in the authenticated dashboard/Link flow. [OAuth guide](https://plaid.com/docs/link/oauth/) · [Historical Marcus announcement](https://plaid.com/blog/changelog-june-2018/)

Statements currently supports depository accounts, not credit-card PDFs. Wells Fargo is listed; Chase requires early-availability access. Marcus/Chime PDF coverage is unverified. Make Statements optional so missing PDF support never blocks transaction linking. [Statements documentation](https://plaid.com/docs/statements/)

Transactions can request up to 730 initial days; available bank history varies. Regular refreshes are typically one to four times daily, and manual refresh cannot force a bank to expose a purchase instantly. Keep local history as it accumulates. [Transactions documentation](https://plaid.com/docs/transactions/)

Integration requirements:

1. Develop with Sandbox. Persist Production tokens securely; reconnect using update mode when supported instead of creating replacement Items unnecessarily.
2. Create Link sessions server-side for the authenticated owner. Exchange public tokens server-side; never send access tokens or the Plaid secret to the browser.
3. Store account IDs under their owning Item and request the desired initial history explicitly.
4. Process `/transactions/sync` added, modified, and removed records. Unique source IDs prevent duplicate imports. Preserve workspace overrides and reconcile pending-to-posted replacement using provider linkage; flag ambiguous cases for review.
5. Stage all sync pages and atomically commit data plus cursor only after the complete batch succeeds. Restart from the original cursor if the provider reports mutation during pagination. Failure must not advance the cursor or leave half a batch visible.
6. Verify Plaid webhook signatures and freshness against the raw request body using its documented verification procedure; durably enqueue work before acknowledging. Webhooks and manual requests use the same sync path.
7. The manual button calls Refresh, then syncs when data becomes available. Show queued, syncing, waiting for bank, reconnect required, or failed state. Distinguish last successful app sync from bank-data freshness. Only the Item owner can refresh its connection.
8. Coalesce duplicate jobs per Item, serialize work for that Item, impose a proposed 60-second manual-refresh cooldown, and honor provider throttling. Add periodic catch-up sync every six hours for missed webhooks, without issuing unnecessary forced Refresh calls.
9. Evaluate budgets after the transaction commit. Persist notification/delivery work so process restarts cannot silently lose alerts.

API behavior must be checked against the official SDK/reference during implementation: [sync integration](https://plaid.com/docs/transactions/) and [webhook verification](https://plaid.com/docs/api/webhooks/webhook-verification/).

## 5. Architecture recommendation

Proposed integration: one Django application with server-rendered pages and bounded React components mounted for Bklit UI charts and selected Kokonut UI interactions. Use Tailwind CSS, Flowbite standard controls, Motion animation, PostgreSQL, and a web manifest/service worker for push. Django supplies authentication, forms, database migrations, and testing. Use supported security patch releases; proposed baseline is Python 3.12+ and Django 5.2 LTS. Django is now user-confirmed; the component integration and remaining infrastructure are proposed. [Django documentation](https://docs.djangoproject.com/en/5.2/) and [Flowbite's Django integration](https://flowbite.com/docs/getting-started/django/).

### Frontend tools and integration

The 2026-09-23 request adds Motion, Bklit UI, and Kokonut UI to the earlier Flowbite selection. It supersedes the blanket restriction on additional UI libraries. The initial Flowbite/Tailwind/Motion build exists; the full React/chart/Insights integration below remains planned and unbenchmarked.

| Tool | Proposed role | Integration boundary |
| --- | --- | --- |
| Flowbite + Tailwind | Navigation, forms, sharing controls, tables, alerts, and ordinary buttons. | Django template includes outside React-owned elements. |
| Bklit UI | Timeline daily/cumulative charts and category-spending charts. | Selected React chart components; server-calculated series plus an accessible HTML table. |
| Kokonut UI | Selected interactive components, initially the Insights request/status action. | Choose a suitable existing component after flow review; preserve its labels, focus, and pending/error behavior. |
| Motion | Brief chart/component transitions and interaction feedback. | Shared animation dependency for React components; honor reduced motion and show confirmed monetary values immediately. |

Documentation reviewed on 2026-09-23: Bklit provides React chart components through a shadcn registry; Kokonut documents React/Next.js installation and Tailwind v4. Motion supports React and plain JavaScript. These libraries do not require replacing Django with Next.js. The proposed React integration is an architectural inference from their component requirements; runtime compatibility has not been tested. [Bklit source and installation](https://github.com/bklit/bklit-ui), [Kokonut installation](https://kokonutui.com/docs), and [Motion documentation](https://motion.dev/docs/react-motion-component).

Build selected component source locally with a Node asset build supporting React/TypeScript; pin compatible React, Tailwind, Flowbite, Motion, and component dependencies at implementation. Scan both Django templates and TSX for Tailwind utilities. Keep one shared theme and React runtime. Registry tooling supplies components; it is not another complete app shell. Use open-source components; premium templates or tools are not assumed. Bklit's chart components are MIT licensed, while its Studio is proprietary. Verify licenses for the specific copied components.

Mount each React component in a dedicated container; Flowbite's DOM initialization must not mutate that subtree. Pass only authorized, bounded data using safely encoded JSON or same-origin authenticated endpoints; retain Django session/CSRF enforcement and server-side permission checks. No frontend library calculates authoritative money totals. Server-rendered values, transaction lists, and chart tables remain useful if enhancement loading fails. Lazy-load charts and share dependencies across components. This approach keeps Django routing and the current deployment model; a separate SPA/SSR service is not required by the tool selection.

Use Motion's reduced-motion configuration and adapt any copied component animations that need additional handling. Avoid count-up effects on financial values, blocking entrance animations, and perpetual decorative motion in core tasks. [Motion accessibility](https://motion.dev/docs/react-accessibility).

### Manus SEO tracking

User clarification on 2026-09-23: "Manus for SEO tracking only; keep Django backend." Manus is the operator tool for SEO audits and tracking on public pages. This does not select the in-app spending-insights provider.

Manus documents SEO workflows using connected data sources for audits, keywords, and rankings. Its website builder separately offers backend/database generation and built-in analytics; its built-in SEO feature applies to websites built and published on Manus. That is not evidence of a drop-in SEO SDK for Django or verified suitability for this app's financial backend. [Manus SEO workflows](https://manus.im/solutions/seo), [website builder](https://www.manus.im/features/webapp), and [built-in SEO documentation](https://manus.im/docs/website-builder/seo).

Proposed scope: an operator connects the chosen public domain and appropriate SEO data source to Manus, records a baseline audit, and reviews changes in indexing, target-keyword visibility, and available organic traffic metrics. Each report records source, reporting window, and collection time; unavailable metrics remain unavailable. Start with manual reports; select an automated cadence only after confirming connector access and costs. A Manus SEO health score is distinct from measured search rankings or traffic.

Only explicitly public informational pages may be indexed or included in SEO tracking. Authenticated workspaces, purchases, reports, statements, invites, and account/AI settings remain access-controlled, carry noindex directives, and are excluded from sitemaps and SEO payloads. Do not send account identifiers, amounts, notes, session tokens, or invitation URLs to Manus or analytics. Robots rules are not access control. Keep SEO work outside the budgeting request path.

There is currently no public domain or public-page scope. Prepare the indexing boundary during implementation; live Manus tracking requires a public surface, connected SEO sources, and any applicable service setup. The current documentation change does not create a Manus project, publish finance pages, or authorize charges. Manus backend generation/hosting is outside the confirmed scope; retain Django and its finance, permission, job, and load-test requirements.

### Backend runtime and jobs

Use the official Plaid Python SDK, a maintained Web Push library, and established encryption/JWT libraries where required. Do not implement cryptography or push protocols from scratch. Verify compatibility and pin concrete versions when scaffolding.

Deploy a modular Django application with separately scalable web and background-worker processes, PostgreSQL, and shared private object storage for PDFs/exports from the start. A small installation can run one web instance, but must also pass multi-instance checks before release. Use database-backed sessions and shared database authorization/rate-limit state; no correctness-critical state or locks may exist only in a process's memory. [Django session backends](https://docs.djangoproject.com/en/5.2/topics/http/sessions/)

Use durable database jobs with retry counts, next-attempt timestamps, deduplication keys, and expiring leases. Claim jobs with short row-locking transactions and `SKIP LOCKED`; perform provider/network work outside those transactions. Recover abandoned leases and serialize sync per Item with a shared lease. Separate sync/push and AI worker pools so a slow generation cannot occupy all operational workers. Use bounded per-user/provider concurrency and shared quotas. [PostgreSQL locking clauses](https://www.postgresql.org/docs/current/sql-select.html)

Web handlers validate and enqueue long syncs, imports, exports, rule backfills, and AI work, returning a status reference for polling. Small interactive edits remain synchronous. Persist all state in PostgreSQL/shared storage so adding a web replica or worker requires configuration, not a permission or job-processing rewrite. No microservices or separate mobile codebase is required to meet this first-release design.

Alternatives considered: a separate SPA/API would add another application to maintain; native mobile apps would duplicate UI work. Reconsider native apps only when a required device capability cannot be delivered reliably through the web app.

### Core records

| Record | Purpose / important constraint |
| --- | --- |
| User | Individual login, verified email, personal preferences. |
| Workspace / Membership | Personal or group context; unique membership, owner/member role; personal workspace has exactly its owner. |
| Invitation | Group, intended email, hashed token, expiry, accepted/revoked state. |
| BankConnection | Owner, provider Item ID, encrypted token, committed cursor, sync state. |
| Account / AccountShare | Account belongs to a user; manual accounts need no bank connection. Bank imports will also reference their owned connection. Unique explicit account-to-group grant. |
| Transaction | Original bank fields, integer cents, date, state, source ID; unique provider ID per connection or CSV source row identity. |
| Category / Rule | Workspace-scoped labels and ordered matching instructions. |
| TransactionAnnotation | Unique transaction/workspace overlay for display name, category, note, and classification; provenance manual/rule/bank. |
| Budget / BudgetState | Workspace, target, period, limit; per-budget/recipient/period baseline and notification marker. |
| Notification / PushSubscription / PushDelivery | Recipient-scoped inbox, device subscriptions, durable per-device delivery attempts. |
| Statement / ImportBatch | Owned account document metadata and private storage key; import identity and preview/commit status. |
| Job | Durable sync/evaluation/delivery work with deduplication key, schedule, and expiring lease. |
| AIConfiguration | Owner, allowlisted provider/model, encrypted credential, daily request/dollar ceilings. |
| AccountAIConsent | Account owner approval for a particular account, workspace, and provider; revocable. |
| InsightRequest / AIUsage | Requester/scope, revisions, minimized input identity, status/result, reserved and actual usage/cost, retention timestamp. |
| Workspace revisions | Data and permission/consent versions for invalidating timeline cursors, derived reports, and AI results. |

Use foreign keys and unique constraints for ownership relationships and deduplication. Scope IDs alone are not authorization: every read/write must validate current membership and account access. Never store a combined global transaction list in a shared browser cache.

Recommended source boundaries: one Django project configuration plus a `budget` app with focused domain modules for sharing/permissions, ledger/imports, rules, reporting/timeline, jobs, notifications, statements, and insights. Keep views thin. Centralize spending arithmetic and authorization rather than reimplementing them in charts, alerts, and prompts. Isolate Plaid and the selected AI SDK at integration boundaries; do not let either dictate domain models. Add database migrations and independent permission/calculation tests as each feature lands. This is a modular application, not one large view/model file or a premature service fleet.

### Capacity and load requirements from the first release

Proposed acceptance targets, subject to hardware benchmarking:

| Dimension | Initial benchmark target |
| --- | --- |
| Dataset | 1,000 users, 1 million transactions over two years, multiple isolated groups, and one 100,000-transaction workspace. |
| Interactive load | 100 authenticated concurrent sessions; sustained 25 requests/second for 15 minutes after warm-up. |
| Server response | Dashboard, timeline page, and filters: p95 under 750 ms and p99 under 2 seconds; unexpected HTTP error rate below 1%. Measure each route, not just the overall average. |
| Operational queue | Sync/push job start delay p95 under 30 seconds at the documented arrival rate; measure provider latency separately. |
| Isolation under load | Zero unauthorized responses, duplicate committed purchases, lost edits, or quota overrun across two web replicas and at least two operational workers. |
| AI interference | The same interactive latency target holds while a separate AI worker waits on a deliberately slow provider mock. |

These are release gates to measure, not claims that code exists or a particular cheap hosting plan can sustain them. Record CPU/RAM, database size, worker count, connection limits, benchmark commands, and results. If a target fails, address the bottleneck or explicitly revise the target; do not describe scalability as verified without evidence.

Create initial indexes for account/date/transaction-ID traversal, workspace/category lookups, membership and shares, notification recipient/read state, and runnable-job scheduling. Enforce source-ID uniqueness. Bound date ranges/page sizes and use database aggregation, bulk import/upsert, and eager related-object loading; a page must not issue a query per purchase. Run query-plan inspection on the seeded dataset before adding summary caches. Stream/export in worker batches rather than materializing all history in web memory.

Use shared object storage, bounded database connection pools, readiness/health endpoints, graceful worker shutdown, and additive/backward-compatible migrations. Rate-limit expensive operations per user/workspace and cap each worker pool so adding replicas cannot exceed database/provider capacity. Persist minimal mutation metadata for sharing/consent changes and integration status to support diagnosis without logging financial content.

Keep a repeatable load harness with synthetic records and mocked providers; never spend real Plaid/AI quota or load-test user bank accounts. Record a two-replica restart/failover exercise, an interrupted worker lease recovery, and access revocation while requests are in flight. k6 thresholds can turn latency/error targets into a failing command. [k6 threshold documentation](https://grafana.com/docs/k6/latest/using-k6/thresholds/)

## 6. Privacy, security, and operations

- Enforce workspace/account authorization on lists, detail pages, mutations, exports, timeline aggregates, AI requests/results, jobs, and statement downloads. Return a consistent not-found response for inaccessible object IDs. Never rely on hidden UI controls.
- Group owners are not entitled to members' private bank accounts. Server operators technically administer the database; this is application access control, not end-to-end encryption.
- Use framework authentication, password hashing, CSRF protection, secure HTTP-only cookies, HTTPS, login throttling, and verified-email recovery. An invitation grants group membership only, never access to another user's identity.
- Keep bank credentials out of the app. Encrypt Plaid tokens at rest using a key stored separately from the database; redact credentials, bank payloads, and push endpoints from logs.
- Service workers cache only public app assets, never account pages, statements, API responses, or session data. Financial responses use private/no-store caching. Unsubscribe a shared device on logout where possible.
- Validate push endpoints and defend server-side delivery against requests to private/internal addresses; use a documented endpoint validation policy and disable arbitrary redirect following.
- Disconnect stops syncing and revokes the Item with Plaid; allow the owner to retain local history or explicitly delete it. Deletion removes related annotations, shares, AI consent/results, PDFs, and derived alerts, then recomputes affected totals and timeline data. Show a confirmation and optional export first.
- Use daily encrypted database/document backups with a proposed 30-day retention, record the retention policy, and rehearse restore before real-data use. On restore, reapply deletions/revocations since the backup before reopening access; retain a minimal deletion/revocation journal for the backup window.
- Track sync success/failures, reconnect needs, stale data, failed push jobs, and backup age. Keep logs free of transaction details.

These are first-release requirements because financial correctness and selective sharing cannot be deferred to a later scale-up.

## 7. Screens

1. Sign in / invitation acceptance and account recovery.
2. Dashboard with workspace switcher, month/year selector, category totals, and budget progress.
3. Transactions with filters, purchase editor, rule creation, and historical match preview.
4. Budgets and categories with merchant/category targets and monthly/yearly periods.
5. Accounts with bank connection state, Sync now, and explicit sharing controls.
6. Reports and owner-only statements with CSV import/export and PDF upload/download.
7. Notifications with unread state and device push setup.
8. Group/settings page with invitations, membership, timezone, and personal preferences.
9. Spending timeline with dated feed, daily totals, cumulative chart, and matching filters.
10. Insights with payload preview, partial-coverage indicator, generate/status/result, provider/key configuration, usage ceilings, and per-account AI consent.

### Phone-first UI and responsive behavior

The main job of the phone UI is to answer what was spent, how much remains, and what needs attention, then let the user inspect or correct a purchase with few taps. Design core flows on a narrow screen first, then use additional space on tablet/desktop. Responsive means both fitting the screen and responding promptly to input.

Design starts with the [low-fidelity wireframes and user flows](../../ux-wireframes.md). Validate navigation, workspace context, action order, disclosure of sharing, and recovery paths before choosing decorative styling. Use neutral grayscale boxes and plain text for this stage; the earlier custom palette/font proposal is superseded. During implementation start with Flowbite defaults and system typography, making small consistent theme changes only after the flows work. Reuse Flowbite's timeline, navigation, cards, forms, progress indicators, dialogs/drawers, tables, alerts, and loading states; do not build an independent design system.

Keep repeated server markup in Django template includes and selected interactive components in React modules. Follow the frontend mapping in section 5 and verify keyboard, focus, touch, and responsive behavior in the actual composition. Use Bklit UI for charts with a separate accessible data table, Kokonut UI for the selected interactive action, and Motion for brief transitions. Document any accessibility adaptation; do not recreate an available component or load a second chart engine for the same view.

Layout and navigation requirements:

- Phone navigation has five labeled destinations: Overview, Timeline, Budgets, Insights, and More. More contains accounts/sharing, statements, and settings; an always-reachable notification button opens the inbox. Show the active personal/group workspace prominently so edits cannot silently land in the wrong group.
- Use a single primary content column on phones. At wider widths, move navigation to a side rail and allow summary/detail columns without changing labels or hiding functionality. Use content-driven CSS grid/flex breakpoints, not device-name checks.
- Reflow from 320 CSS pixels through tablet and wide desktop without whole-page horizontal scrolling. Transaction rows become stacked labeled entries on phones and may become a semantic table on desktop. Long merchant names wrap; amounts, signs, and action buttons stay legible. Dense data gets an explicitly labeled local scroll region only where reflow would lose meaning. [W3C reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
- Use at least 44 by 44 CSS-pixel hit areas for interactive controls, with spacing between destructive and common actions. Keep form text at least 16 CSS pixels; preserve pinch zoom and support 200% text enlargement. No functionality may depend only on hover, swiping, dragging, or color.
- On phones, transaction editing is a dedicated full-screen page with labeled fields and an obvious Save changes action; filters use a compact accessible dialog or page. Preserve list position and filters when navigating back. Warn before discarding a dirty form. Larger screens may use an adjacent detail panel without changing the permission/save behavior.
- Respect display cutouts and the home indicator with safe-area padding. Bottom navigation and sticky actions must not cover content or fields when the virtual keyboard opens; use dynamic viewport sizing with a fallback and test browser toolbar expansion/collapse. [WebKit safe-area guidance](https://webkit.org/blog/7929/designing-websites-for-iphone-x/)
- Persist workspace, period, and filters in shareable/authenticated page URLs where appropriate. Native browser Back/Forward and reload must work. Never include API keys or sensitive raw purchase text in URLs.

Charts, feedback, and accessibility:

- Make timeline chart points selectable by tap and keyboard, with a visible selected-date summary and equivalent table/list. Reduce tick-label density on narrow screens; never shrink text until unreadable. Day/week/month aggregation may change presentation, but displayed totals always use the same accounting calculation.
- Show an immediate pressed/loading state for sync, save, filter, and AI actions. Keep submitted form values after validation/network failure, identify errors beside fields, and announce status changes without stealing focus. Only show Saved or Sync complete after confirmed success; do not optimistically change financial totals.
- Preserve reserved layout space while loading; use lightweight skeletons or progress text without flashing or indefinite unexplained spinners. Show actionable empty, offline, retry, reconnect-bank, and denied-notification states. Cancel outdated filter requests so late responses cannot overwrite the current selection.
- Use semantic landmarks, real labels, visible focus, appropriate dialog focus/return behavior, and screen-reader descriptions. Respect reduced-motion preferences; motion is brief and functional. Verify keyboard, VoiceOver, and TalkBack paths for the core tasks.
- Home-screen mode has the same navigation and permissions as browser mode. Provide platform-appropriate installation/push instructions only when relevant. Offline mode explains the connection requirement; it never pretends a bank sync or edit succeeded, and it does not persist private finance pages in the service-worker cache.

### Mobile quality and performance gate

Verify every core flow at 320, 360, 390, 430, 768, 1024, and 1440 CSS-pixel widths, including phone landscape, 200% text zoom, long names, large currency values, empty datasets, and keyboard-open forms. Review actual screenshots of Overview, Timeline, purchase editing, budgets, sharing, and Insights at phone and desktop sizes. Browser emulation supplements real-phone checks but does not replace them.

Test current stable iOS Safari and Android Chrome on actual phones, plus desktop Safari, Chrome, Firefox, and Edge. Record browser/OS versions. Test installed home-screen mode where supported, invitation acceptance, bank-link return/cancellation, file upload, push permission, and notification deep links after login. Existing platform limits on Web Push still apply.

Proposed performance targets: LCP at or below 2.5 seconds, INP at or below 200 ms, and CLS at or below 0.1 at the 75th percentile when field data is available. Before launch, use a documented mid-range Android/4G lab profile and measure key interactions directly; lab results are not field percentiles. These browser-experience targets complement, rather than replace, the server/load targets in section 5. [Core Web Vitals definitions](https://web.dev/articles/vitals)

Prefer server-rendered useful content, minimal JavaScript, paginated feeds, compressed assets, and lazy loading of nonessential chart/AI UI. Proposed initial-route budget remains at most 150 KiB compressed app-delivered JavaScript, including any loaded React, Flowbite, Motion, Bklit, Kokonut, and transitive dependencies. Record initial and deferred bytes separately; the expanded frontend makes this target a specific measurement risk, not a verified result. Load third-party Plaid assets only when connecting/reconnecting. No chart or AI library should block viewing purchases. Measure the actual asset/network trace and long main-thread tasks, use selected component imports, and explicitly revise the target if evidence requires it.

## 8. Growth without a rewrite

The first release supports finance sharing with partners and friends. A friend can be invited into a chosen group and share selected accounts there; they receive no access to other groups or private finances. Use the same membership/permission system at two users or a thousand. Initial enrollment may still be just the couple. Public registration remains disabled.

The ten-Item Trial cap applies to the whole Plaid team/application, not ten per user or group. Adding friends may require paid access even when the app itself handles the traffic. Pay-as-you-go currently has no minimum commitment, but exact product prices must be checked in the dashboard; upgrading is a separate owner decision. [Pricing documentation](https://plaid.com/docs/account/billing/)

| Trigger | Smallest next change |
| --- | --- |
| More than ten created Production Items | Review paid Plaid pricing and obtain an explicit spending decision before upgrade. |
| Queue delay approaches the tested limit | Increase the relevant worker pool within provider/database limits; use a queue service only if database queue contention is measured. |
| Report latency approaches the tested limit | Inspect query plans; add measured indexes or revision-aware summaries with immediate permission invalidation. |
| More interactive capacity needed | Increase web replicas using the already shared storage/session state; repeat the load gate. |
| AI quota or cost ceiling reached | Show the limit and allow the key owner to change it explicitly; never borrow another member's key or silently increase spending. |
| Required mobile capability is missing | Evaluate a native wrapper/app for that concrete requirement. |
| Public launch instead of invited friends | Separate work for onboarding, operational support, abuse controls, provider requirements, and legal/privacy review. |

Deferred: billing users, public signup, social feeds, settlements, card issuing/blocking, investment trading or advice (read-only net worth and investment monitoring was requested on 2026-09-25), multiple currencies, arbitrary custom fields, autonomous AI rule/ledger edits, scheduled AI generation, multiple AI providers, OCR, and microservices. Read-only AI insights, finance-sharing invitations, and the spending timeline are in the first release.

## 9. Release acceptance

- Two users connect Sandbox accounts; personal data is isolated until a specific account is shared.
- A third user in another group cannot discover records through IDs, search, totals, exports, notifications, or files.
- Share revocation and member removal remove access immediately, including pending push delivery.
- Repeating sync/webhook jobs produces one purchase; pending-to-posted replacement preserves edits without double counting.
- Failed paginated sync leaves the old cursor/data intact; retry completes correctly.
- A purchase, credit-card repayment, internal transfer, refund, and pending item produce independently verified totals.
- Manual edits survive bank corrections; rule preview/backfill preserves manual overrides and respects workspace boundaries.
- A threshold crossing produces one inbox alert and eligible device deliveries; retries and recrossing do not duplicate inbox alerts.
- Sync now displays honest completion/failure/reconnect states and does not imply live bank data.
- CSV reimport and overlap review preserve legitimate duplicate purchases; malformed files fail before partial import.
- PDF access remains owner-only even if its account is shared.
- Push works on both users' actual phones, and denied permission leaves the inbox usable.
- HTTPS deployment, redacted logs, token encryption, and backup restoration are verified before connecting real accounts.
- A friend joins a shared group, contributes chosen accounts, and collaborates on its budgets without seeing either person's private accounts or other groups.
- Timeline daily totals and cumulative values match reports through refunds, zero-spend days, pending replacement, year boundaries, paging, and concurrent updates.
- AI key ownership and separate per-account/provider consent are enforced at dispatch and result access; missing consent yields a clearly labeled partial analysis.
- AI failures, malicious labels, unsupported fact references, cost reservations, concurrent requests, and revocation during generation are covered by deterministic tests using a fake provider.
- Core budgeting works without AI. AI output never changes the ledger or becomes the financial calculation source.
- The documented multi-instance and load benchmark passes, with hardware and results recorded, before scalability is called verified.
- Core flows pass the phone/tablet/desktop width matrix, real iOS/Android browser checks, keyboard-open and enlarged-text cases, and screenshot review without hidden controls or whole-page overflow.
- Timeline charts, purchase editing, sharing, and notifications are touch/keyboard accessible; browser Back preserves context and slow-network errors preserve user input.
- Mobile loading/interaction/layout-shift measurements and asset sizes are recorded against section 7 targets before mobile performance is called verified.
- The low-fidelity journeys are reviewed before visual polish; implemented UI patterns follow the Flowbite/Bklit/Kokonut/Motion mapping. Reduced-motion behavior, React/Flowbite ownership boundaries, and chart-table equivalence are checked.
- Private finance routes remain authenticated, excluded from public sitemaps, and absent from Manus/SEO payloads. When a public site is available, record a Manus baseline report and verify its actual connected sources before claiming tracking works.

## 10. Review notes

The defaults in section 2 and unimplemented architecture in section 5 remain proposals. The implementation snapshot distinguishes current code from full-release requirements. Installed foundation versions are recorded in requirements.txt/package-lock.json and the development guide. For a synthetic-data preview the user chose Render's free web service (deploys from GitHub after CI passes) with a separate Neon database; see [operations](../../operations.md). The real-data host, domain and production credentials remain unselected; no cost or provider enrollment is authorized by this document.
