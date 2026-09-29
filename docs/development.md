# Local development and verification

Updated 2026-09-25. Development-only foundation, not ready for real financial data.

## Where to work

Use `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation` on branch `feat/project-foundation`. On 2026-09-28 it was merged into `main`, which now holds the whole app and is what Render deploys. On each requested push, `main` is fast-forwarded to `feat/project-foundation` and both are pushed (see `AI_HANDOFF.md`).

## Setup (PowerShell)

Python 3.14.6 is at `C:/Users/bmauricio/AppData/Local/Python/pythoncore-3.14-64/python.exe`; WindowsApps python/py aliases fail. Node 22.23.1/npm 10.9.8 are available. Existing PostgreSQL 17 was discovered but not changed or authenticated to.

From the implementation worktree:

```powershell
& 'C:/Users/bmauricio/AppData/Local/Python/pythoncore-3.14-64/python.exe' -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm.cmd ci
npm.cmd run build
$env:DJANGO_DEBUG = '1'
$env:BUDGET_LOCAL_SQLITE = '1'
$env:DJANGO_SECRET_KEY = & .venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(48))'
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`. No admin route or public registration exists. The operator-created user signs in, creates a group and uses Invite someone. In DEBUG mode, invitation/setup/verification/recovery email prints to the server console; no message leaves the machine. New invitees request a separate setup email and open its link before choosing a username/password; then sign in and explicitly join. Existing users verify their current email through the header link. Password recovery is available for verified addresses only. Do not expose runserver publicly. Supply a stable secret through the environment to persist sessions across restarts; never commit it. .env.example is a reference, not auto-loaded.

Apply migrations 0002-0005 (`manage.py migrate`) before using invitations and transactions. Nonempty user emails become case-insensitively unique; resolve any duplicate existing emails deliberately before migration (none were found in the synthetic local database). Existing accounts are not automatically marked verified. Accounts with no email or a forgotten password before verification need operator assistance; invitation-created accounts now prove mailbox control before creation.

Production defaults to Django's SMTP backend, configured through `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`. `DJANGO_EMAIL_BACKEND` can explicitly select another Django backend. No SMTP credentials or provider are configured here. Invitations expire after seven days; setup, email verification and password recovery links after one hour. Sending auth email has a shared database cooldown of one minute per user, setup mail one minute per invitation, and new invitations one per address/minute plus twenty/group/hour. These are initial abuse bounds, not a measured delivery-capacity claim.

For PostgreSQL, unset BUDGET_LOCAL_SQLITE and set the PG variables from .env.example. The development database is hosted on Neon (free plan, project `dry-sea-53765016`, us-west-2, database `budgetdb`, direct non-pooler host, `PGSSLMODE=require`). The user keeps `PGUSER`/`PGPASSWORD` in ignored `.local/neon.env`; `.local/neon-env.sh` (ignored, Git Bash: `. .local/neon-env.sh`) loads it, sets host/database/SSL and a throwaway secret without printing credentials. Synthetic data only until release gates pass. The local PostgreSQL 17 service is not used. SQLite is rejected with DEBUG off; passing SQLite checks do not prove row-locking or multi-instance correctness.

## Checks

```powershell
.venv/Scripts/python.exe manage.py test --settings=config.test_settings --noinput
.venv/Scripts/python.exe manage.py check --settings=config.test_settings
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.test_settings
npm.cmd run build
```

config.test_settings is synthetic-test-only: public test secret and fast password hashing. Never use it for personal data/deployment.

Browser checks require locally installed Google Chrome. Stop the ordinary development server first, then start the test-only server in one terminal:

```powershell
.venv/Scripts/python.exe tests/browser/server.py
```

To look around by hand, open http://127.0.0.1:8000 and sign in as `browser-check` / `synthetic-browser-check-only` (public synthetic credentials). `.venv/Scripts/python tests/browser/seed_demo.py [--reset]` adds made-up demo accounts and six months of transactions to that user. Run `npm.cmd run test:browser` in another terminal, then stop the server with Ctrl+C. The helper migrates a separate `.local/browser.sqlite3`, seeds the existing synthetic browser account, generates an ephemeral secret and forces console-only email. It redirects console email to `.local/browser-server.log` and request/error logs to `.local/browser-server-errors.log`; the invitation browser test reads only these local synthetic emails. Tests add synthetic accounts/groups per run. All databases, mail tokens, screenshots and results stay in ignored `.local/`. Never use these deliberately public synthetic credentials or this server with private records.

## Previous foundation checkpoint — September 23

- 27 Django tests passed; initial access tests and the later sharing-label regression were observed failing before their fixes. Framework check and migration drift check passed.
- 2 Playwright tests passed in Google Chrome 153.0.8010.53 on Windows: sign-in/account creation/sharing, reflow at 320/360/390/430/768/1024/1440px, reduced motion, and JavaScript-disabled login/account creation. Phone (390px) and desktop (1440px) screenshots were opened and reviewed. This is not actual-phone or full accessibility certification.
- Asset build passed: JS 15.42 kB / 4.96 kB gzip; CSS 58.04 kB / 11.28 kB gzip. Vite estimates, not network/performance measurements. React/chart runtimes are not in the current entry.
- Independent review reran the then-current 26 tests, found account-label ambiguity (fixed and regression-tested) and a minor missing personal data-revision update on account creation (deferred until before derived outputs).
- Browser sign-in regression was reproduced, then fixed with same-origin referrer policy; CSRF remains enabled. Sharing labels now identify owned accounts by name without leaking others' private labels. See [Django referrer-policy/CSRF guidance](https://docs.djangoproject.com/en/5.2/ref/middleware/#referrer-policy).
- Production-mode `manage.py check --deploy` passed with a generated ephemeral secret and PostgreSQL configuration; this checks settings, not database connectivity or deployment readiness. `pip check` passed; `npm audit --omit=dev` reported zero known vulnerabilities at this run.
- Development server was stopped at the checkpoint. Ignored local SQLite data contains only synthetic browser records; start it again using the setup commands above.
- No PostgreSQL, multi-process, actual-phone, screen-reader, financial correctness or load benchmark has run.

## Dependencies and boundaries

Pinned Python runtime packages include Django 5.2.17, django-axes 8.3.1 and psycopg 3.3.6; all versions in requirements.txt. Frontend: Flowbite 4.0.2, Tailwind 4.3.3, Motion 13.4.1, React/React DOM 19.3.0, TypeScript 7.0.2, Vite 8.3.0. Exact transitive versions are in package-lock.json. TypeScript 7 paths are relative and omit removed baseUrl.

Installed Flowbite, Tailwind, Motion, React/React DOM and Vite package metadata declares MIT licenses. No Bklit/Kokonut source has been copied yet; verify each component license when added. Registry addresses follow [Bklit installation](https://ui.bklit.com/docs/installation) and [Kokonut installation](https://kokonutui.com/docs). npm uses a worktree-local ignored cache; the default user cache is inaccessible in the sandbox.

There is no CDN compiler, chart runtime, bank SDK, AI provider or Manus connection. Application responses carry private/no-store and noindex headers; robots.txt disallows crawling. These supplement authentication, never replace it. Only login and minimal health/readiness are public; no analytics payload is sent.

## Invitation continuation — September 24

- 40 Django tests pass, including thirteen new invitation/recovery checks. Initial nine tests failed on absent routes before implementation. The review-found signup email-squatting regression and overlong-email regression each failed before their fixes, then passed. A further regression showed that older pending invites were unreachable; the owner list now uses Django pagination (20/page). Framework and migration drift checks pass.
- Fresh read-only review independently ran the then-current 36 tests and identified both issues above. Mailbox proof now precedes identity creation; invitation emails are validated against the model's 254-character bound. Fixes were verified by tests rather than a second review.
- Membership notices appear only for their recipient in a currently accessible group; full unread inbox/push remains milestone 5. Inviting/joining does not share a new member's accounts. Member removal revokes their shares and pending invitations for that email.
- Frontend build passes with unchanged JS at 4.96 kB gzip and CSS at 11.29 kB gzip. All three Chrome browser tests pass, including mailbox setup, invited registration, explicit join and leaving with JavaScript disabled, plus the existing sharing/reduced-motion checks. Invitation owner screens reflow at 320/360/390/430/768/1024/1440px. No new runtime dependency was added.
- All email checks use synthetic in-memory or console delivery. No real messages, SMTP delivery, PostgreSQL row locking, actual-phone testing, or load measurements are claimed.
- Final invitation browser rerun passed after pagination; phone and desktop screenshots were opened and reviewed. Production-mode `check --deploy` passed (settings only). Test server was stopped. Initial Windows process-launch/automatic browser-server lifecycle attempts failed; the direct Python helper documented above was used for successful checks.

## Transactions slice — September 24 (later)

- 51 Django tests pass. Each new test failed first: account-creation revision (0 != 1), private-storage setting missing, transaction import error.
- `reporting.spending(user, workspace, start, end)` is the single spending calculation: posted expenses minus refunds; pending separate; income separate; transfers/card payments never count. Group totals use `visible_accounts`, so private accounts are excluded.
- Private files: `BUDGET_PRIVATE_STORAGE_ROOT` (default ignored `.local/private-files`); no URL route serves it. Multiple replicas need a shared mount or object-store backend — decide with the host (milestone 7).
- 3/3 Chrome browser checks pass. Transaction form, account list and month summary checked at 360px with no horizontal overflow; screenshots in ignored `.local/txn-*.png` were reviewed. Form select now shares input styling; Type defaults to Expense. Asset build: CSS 11.43 kB gzip, JS unchanged 4.96 kB.
- Known limits: account page shows newest 100 rows only (cursor paging lands with the timeline). Pre-existing: the workspace switcher list gets long on phones once there are many groups.

## Annotations and apple-design pass — September 24 (evening)

- 54 Django tests pass. Three new annotation tests; two failed first on the missing route (404 != 302), the third (member denied) passed trivially before the route existed and now guards it. Migration drift check clean.
- Annotations: `TransactionAnnotation` unique per (transaction, workspace). Account rows open an annotation page (Edit) that links to "Edit original entry". Notes are labelled Personal note / Group note. Only the account owner may annotate (same rule as editing purchases).
- apple-design pass (skill principles through existing Tailwind CSS, no new dependency): instant `:active` press scale 0.97/100ms on buttons/links (transform dropped under `prefers-reduced-motion`, colour feedback kept), row press background, negative tracking on h1/h2, `prefers-contrast: more` darkens gray-600 text and gray-200/300 borders via theme tokens, `aria-current` on the bottom nav. No translucent surfaces exist, so reduced-transparency needs nothing yet. Motion message flash is a 200ms colour tween, left as is.
- Checked in Chrome at 360px: annotation form and list screenshots (`.local/annot-*.png`, including contrast-more) reviewed; no horizontal overflow; pressed transform measured `matrix(0.97…)`; 3/3 browser tests pass on a restarted server (which was then stopped). Asset build: CSS 11.60 kB gzip, JS 4.96 kB.
- Still open: the workspace switcher list grows long on phones (visible in the screenshots after many synthetic groups).

## Hosted PostgreSQL — September 24 (night)

- User chose Neon over hosting locally. A password pasted in chat was reset by the user before use; the new one lives only in ignored `.local/neon.env`.
- `migrate` applied 0001-0005 to `budgetdb`. Full suite on Neon (PostgreSQL 17.11): **58/58** in ~71 s; the test database is created and dropped automatically. On SQLite: 58 run, 4 PostgreSQL-only tests skipped.
- `budget/tests/test_concurrency.py` (threads = separate DB sessions, the same isolation two web processes get; not separate OS processes): share-vs-removal, parallel invites, parallel accepts, session read across sessions. With the workspace locks removed, three of the four failed (leaked share, two invitations, two accepts); restored code passes.
- Not measured: load, latency (the database is in Oregon), multiple app instances, connection pooling.

## Transaction list and yearly view — September 25

- 70 Django tests (66 run, 4 PostgreSQL-only skipped on SQLite); `test_reporting` 24/24 also on Neon PostgreSQL. New tests failed first (missing `monthly`, missing route, 404s), then passed.
- `workspaces/<id>/transactions/`: search (original description or this workspace's display name — never another workspace's), account, person and From/To filters; newest first, 50 per page with a `(date, id)` keyset cursor (`before=YYYY-MM-DD_id`); malformed cursor → 404, invalid filters → 400 with inline errors. Query count is the same for 1 and 62 rows. Only owners see Edit; Edit returns to the filtered list via a validated relative `next` (external URLs fall back to the account page).
- Workspace summary takes `?period=YYYY-MM` or `?period=YYYY` (anything else → this month) with previous/next and Month/Year links. Year view adds a per-month table from `reporting.monthly()` (one grouped query); the test asserts every month and the year sum equal `spending()`.
- Found by the browser run: the fixed bottom nav covered a submit button once the workspace list got long; fixed with `scroll-padding-bottom` on `html`. 4/4 Chrome checks pass, including a new `tests/browser/transactions.spec.ts` (search → edit → back to filtered list; reflow 320–1440px). 360px list/year screenshots reviewed. CSS 11.72 kB gzip, JS 4.96 kB.
- Limits: no category filter (milestone 4); no filtered totals on the list (timeline slice); cursor is not yet invalidated on data-revision change (timeline slice).

## Timeline, More page and standalone invites — September 25 (later)

- 78 Django tests (74 run + 4 PostgreSQL-only skipped on SQLite); `test_reporting`, `test_timeline`, `test_invitations` 45/45 on Neon. New tests failed first (missing routes, missing `daily`).
- **Timeline** (the `transactions` route, now titled Timeline): empty From/To mean one calendar month (this month; To's month; From's month); ranges over 731 days are rejected. `reporting.daily(rows, start, end)` is one grouped query, zero-filled, with a running posted total; the plan fixture gives daily `[10000, 0, -1500]` and cumulative `[10000, 10000, 8500]`, and sums equal `spending()`. Range totals and a collapsible daily table (the accessible data behind the future Bklit chart) use the same filters as the feed. The feed has day headers with each day's net. Cursor links carry `rev=<data_revision>-<permission_revision>`; a stale cursor restarts from newest with a status message.
- **Standalone invites**: an Invitation on the inviter's personal workspace (no migration). It reuses the token, mailbox-proof setup and registration flow; accepting creates no membership, so the new login sees only its own Personal workspace. Only the owner can send or revoke. Reached from More or the Personal page ("Invite someone to Budget").
- **More page** (`more/`): username, email + verified status, Change password (Django `PasswordChangeView` at `settings/password/`, session kept), Email verification, Sign out; Add account, New group, Invite someone to Budget. The header now shows only the username.
- **Navigation**: bottom nav is Overview | Timeline | More. The workspace switcher is a native `<details>` ("Workspace: <name>"), one line when closed, which fixes the long list on phones.
- Build CSS 11.82 kB gzip, JS 4.96 kB. 5/5 Chrome checks (new standalone-invite journey with JavaScript disabled). 360px screenshots of Timeline, More and the switcher reviewed; no overflow at 320/360 (plus the existing width matrices).
- Not done: email change while signed in (operator), a page-size parameter (fixed 50), web-based first-user setup (still `createsuperuser`).

## Online preview configuration — September 25

- User chose Render (free) for a public preview URL with synthetic data only; GitHub Actions runs CI, it does not host. Setup steps: [operations guide](operations.md).
- Added `gunicorn` 26.2.0 and `whitenoise` 6.12.0; `render.yaml`; `.github/workflows/ci.yml`; `.python-version` (3.14). Settings: WhiteNoise middleware and compressed manifest storage when DEBUG is off; `RENDER_EXTERNAL_HOSTNAME` joins ALLOWED_HOSTS; `SECURE_PROXY_SSL_HEADER` only with `BUDGET_BEHIND_PROXY=1`; `/health/` and `/ready/` exempt from the HTTPS redirect.
- Checked locally: 78 tests OK; `check --deploy --fail-level WARNING` clean with production env; `collectstatic` post-processes; in production mode the hashed CSS is served 200 with immutable caching, `/health/` 200 over HTTP, pages 301 to HTTPS, proxied HTTPS 200, unknown host 400. Gunicorn itself does not run on Windows, so it is first exercised on Render.

## Next

## Timeline chart — September 25 (night)

- First mounted React component: a Bklit `AreaChart` of the running posted total (`assets/spending-chart.tsx`) on the Timeline. Data comes from the page's `reporting.daily()` series via `json_script` (`daily-series`); the tooltip shows the running total and that day's net. The daily totals table stays as the accessible equivalent; the chart container is `role="img"` with a summary label and stays `hidden` if the script fails or JavaScript is off.
- Bklit source (MIT, copyright uixmat) copied from the registry into `assets/components/charts/`, `assets/components/shimmering-text.tsx` and `assets/lib/utils.ts` (only the area-chart item and its registry dependencies). One import path was fixed to `@/components/shimmering-text`. Added pinned deps: `@number-flow/react` 0.6.2, `@visx/{curve,event,grid,responsive,scale,shape}` 4.0.1-alpha.0 (the registry's pinned version), `clsx`, `d3-array`, `d3-shape`, `tailwind-merge` (MIT/ISC). Chart theme tokens (`--chart-*`) are defined in `assets/app.css` on the gray palette.
- `vite.config.ts` now does a normal app build (was library mode, which skipped minification and left development React): `base: "./"` so the lazily imported chunk resolves beside `app.js`. Measured: initial `app.js` 4.63 kB gzip, CSS 12.51 kB gzip; deferred `spending-chart-*.js` 162.56 kB gzip, loaded only when a page has `[data-spending-chart]`. Mostly React DOM and Motion's React build. Initial budget (150 KiB) holds; the deferred cost is recorded, not yet optimised.
- Reduced motion: `MotionConfig reducedMotion="user"` and a zero reveal duration. After a resize the chart re-measures after a short debounce, so the browser width checks poll.
- Verified: 78 Django tests OK (4 PG-only skipped), `check` clean, build OK, production-mode `collectstatic` OK, 5/5 Chrome checks (Timeline spec asserts the chart SVG renders); 360px screenshot reviewed (`.local/transactions-phone.png`, `.local/chart-dbg.png`).
- Not done: keyboard access to chart points (the table covers it), a y-axis, category charts (milestone 4).

## Visual theme — September 25 (night)

- User-supplied palette (more colours to come): Bubblegum Pink `#f45b69`, Lavender Blush `#f6e8ea`, Coffee Bean `#22181c`, Black Cherry `#5a0001`. Light mode is white cards on Lavender Blush; dark mode (follows the OS) is Coffee Bean with cherry-tinted cards and Black Cherry borders.
- All colours are defined once at the top of `assets/app.css` (palette block), mapped to roles (`--canvas`, `--surface`, `--ink`, `--muted`, `--line`, `--accent`, `--accent-text`, `--danger`, ...), and exposed as Tailwind utilities (`bg-surface`, `text-muted`, `border-line`, ...). Templates no longer use gray/white/red utilities. To add a colour: add it to the palette block, then point a role at it.
- Contrast: white text on the pink fails (3.2:1), so buttons and the active nav pill use Coffee Bean text on pink (5.4:1). Links are Black Cherry in light mode and pink in dark. `prefers-contrast: more` darkens muted text and borders.
- (Superseded later the same night by the Robinhood-style layout: fonts reduced to Hanken Grotesk, receipt style removed.) Type (self-hosted via Fontsource, OFL): Young Serif for page titles and the wordmark only; Hanken Grotesk for body; Martian Mono (condensed width) for money amounts (`.amount`).
- Signature: spending summaries on Overview and Timeline are receipts (`.receipt`): perforated bottom edge (CSS mask), dashed rule, and label-left/amount-right lines on phones.
- Also: translucent bottom nav (solid under `prefers-reduced-transparency`), rounded cards (`.card`), pill workspace links, flash message fades from the accent to the themed background (was hard-coded white). Flowbite form defaults are overridden with an `:is()` selector so selects follow dark mode; Flowbite's `--color-brand`/`--color-body` map to the accent/muted roles.
- Measured: CSS 15.97 kB gzip (fonts load separately, latin subsets only in practice); initial JS 4.64 kB gzip. 78 Django tests OK (4 PG-only skipped); 5/5 Chrome checks; light and dark 390px screenshots reviewed (`.local/d-{light,dark}-{login,overview,timeline,receipt}.png`).
- Gotcha: `tests/browser/server.py` runs without the reloader, so Django's cached template loader keeps old templates; restart it after template edits.
- Not done: a manual light/dark toggle (OS setting only), restyling the chart tooltip beyond tokens, a real-device check.

## Robinhood-style layout — September 25 (night, later)

- User asked for a UI "more like" a Robinhood reference (three phone screens). Superseded the receipt signature and the serif/mono fonts (Young Serif and Martian Mono removed; Hanken Grotesk only).
- Flat layout: no bordered cards (`.card` is spacing only); light canvas is white, dark is Coffee Bean; hairline `stat-row` label/value rows; pill-shaped primary buttons.
- Overview: workspace name, the period's posted spending as a big number (`.hero-amount`), change versus the previous month/year (one extra `spending()` query), the running-total chart directly below with no grid or axis, then period chips (←, Month, Year, →). Accounts list rows end in a pink value pill with each account's posted spending for the period (one grouped query). Year view feeds the chart a monthly running total.
- Timeline: same hero number + chart, stat rows, filters folded into a `Filters` disclosure (open when filters are set or invalid), back link is a `‹ Workspace` chip (accessible name still "Back to …").
- Bottom nav: inline SVG icons with labels; the current item turns pink.
- Chart containers clip overflow; the chart re-measures after a resize, so browser width checks poll.
- Verified: 78 Django tests OK (4 PG-only skipped); 5/5 Chrome checks; light/dark 390px screenshots reviewed (`.local/r-{light,dark}-{overview,timeline}.png`). CSS 15.83 kB gzip, initial JS 4.64 kB gzip, chart chunk 158.87 kB gzip.

## Settings, login changes, CSV export, theme — September 25 (night, latest)

- **Settings** (`settings/`, replaces More; `more/` redirects) groups Your login, Appearance, Your data and Add, then Sign out. The bottom nav item is Settings.
- **Login changes** need the current password. Username (`settings/username/`) and password (`settings/password/`) change right away, then `budget/account_mail.notify` emails the *verified* address ("if this wasn't you, reset your password"). No verified email means no notice; a failed notice never undoes a change.
- **Email change** (`settings/email/`) sends a signed one-hour link (`django.core.signing`, no migration) to the new address and a notice to the old one; nothing changes until the link is confirmed (POST, signed in as the same user). The link carries an HMAC of the password hash, so a password change or reset voids it. Confirming sets email and verified email; an address taken in the meantime is a form error. Uses the existing one-minute `claim_email_send` limit.
- **CSV export** (`workspaces/<id>/transactions/export.csv`): the Timeline's rows with the same filters, default month and two-year cap, unpaged, newest first. Columns: Date, Account, Owner, Name (workspace name if renamed), Original description, Classification (effective), Status, Amount (USD, positive; the classification gives the direction), Note (this workspace's only). Cells starting with `= + - @` are quoted against spreadsheet formula injection. `Cache-Control: no-store`. The Timeline has an Export CSV chip; Settings links this month's personal export.
- **Theme**: System / Light / Dark on Settings, stored in `localStorage` (this device only). An inline script in `<head>` applies it before paint via `html[data-theme]`; CSS dark roles apply for `data-theme="dark"`, or the OS setting unless `data-theme="light"`. Without JavaScript the picker is hidden and the OS setting applies.
- Measured: 93 Django tests OK (4 PG-only skipped), 6/6 Chrome checks (new `settings.spec.ts`: theme survives reload, CSV downloads), `check` and `makemigrations --check` clean, JS 4.79 kB gzip initial. Light/dark Settings screenshots reviewed.
- Not built: CSV import, per-account theme sync, sign out other devices, account deletion.

## Speed and app-feel pass — September 25 (night, latest)

Why: the user asked which agency-style speed wins apply (WebP/AVIF, lazy loading, CDN, trimming scripts, Next.js + headless CMS, SSR), and for skeleton loaders and preloading so the phone experience feels like an app.

What applied and what didn't:
- Already true: server-side rendering (every page is Django HTML and works without JavaScript) and lazy loading (the chart code loads only on chart pages, after render).
- Not applicable: there are no images (icons are inline SVG), and a headless CMS is for marketing content. Replacing Django with Next.js would add weeks of work for no measured gain.
- CDN: hashed static files already get `max-age=315360000, immutable` and gzip from WhiteNoise. Private pages stay `no-store`, and no CDN may cache them.

Measured (lab only, not field data):
- Setup: production-mode local server (DEBUG off, WhiteNoise manifest pipeline, synthetic SQLite, 300 synthetic transactions), Chrome with Slow 4G (150 ms RTT, 1.6 Mbps) and 4x CPU throttling, 390 px viewport. The measuring spec and server script were temporary.
- **Found and fixed a production-only bug.** The chart chunk imported shared Motion code from `./app.js`, while Django served the page `app.<hash>.js`. The browser therefore loaded and ran the entry twice: two chart mounts, two theme listeners, and an extra 5 kB download. Dev used one URL, so it never showed. The message flash now uses native `element.animate` (what `motion/mini` wraps), so the entry shares nothing with the chart. Initial JS went from 4.79 to **1.17 kB gzip**.
- **Chart skeleton.** A server-rendered slot with the chart's 2.4:1 aspect ratio holds a faint pulsing line (static under reduced motion) until the chart mounts. Page shift (CLS): Overview **0.117 → 0**, Timeline **0.096 → 0**. The slot is 149 px tall both before and after mount, in light and dark. Without JavaScript the slot is not shown (a `js` class on `<html>`), and a failed chart load removes it.
- **Preloading.** Speculation rules (Chrome/Edge/Android; other browsers ignore them) prefetch the bottom-nav pages as soon as a page loads, and any other same-origin link on hover or touch. CSV export and `[download]` links are excluded, and GET pages have no side effects. Every tab switch was confirmed as served from the prefetch (`deliveryType: navigational-prefetch`), and `no-store` did not block it. Prefetched pages can be up to 5 minutes old (Chrome's limit); a new page load re-prefetches.
- **Page crossfade.** Cross-document view transitions (Chrome, Safari 18.2+) crossfade between pages, the bottom nav holds still, and they are off under reduced motion. The head script opts in only when JavaScript runs: with JavaScript disabled, this Chrome left the page stuck behind the transition overlay, which broke the no-JavaScript browser checks.
- **Installable.** A web app manifest (standalone display) plus an icon set (SVG, 180/192/512 PNG: the running-total line in Coffee Bean on Bubblegum Pink) and light/dark `theme-color`. On a phone, Add to Home Screen opens full screen without browser chrome. There is deliberately no service worker, so no financial page is ever stored offline.
- **Font preload tried and dropped.** An A/B test with and without it showed no LCP difference (login 0.91–1.04 s vs 0.92–1.03 s); the font already uses `font-display: swap`.
- Timings on this machine were noisy between runs (login LCP 0.9–2.1 s). Every run met the LCP ≤ 2.5 s target, and view transitions on vs off were within noise. Deterministic results: CLS 0, a single entry load, 1.17 kB initial JS, and prefetched tab pages.
- **Chart flash fix (same day, after user report).** The user saw the line appear before its draw-in and suspected the preload. Screencast frames showed two causes: the page crossfade faded the *previous* page's finished line over the new page, and the faint placeholder line showed briefly. Fixes:
  - The chart slot has its own `view-transition-name`, with no old snapshot and no group or new animation, so the old line vanishes instantly and only the new line draws in.
  - The placeholder line now appears only if the chart takes more than 0.4 s, which prefetched pages essentially never do.
  - Re-captured frames confirm no line before the draw-in. 6/6 Chrome checks.
- **Second chart flash fix (after categories, user report: "rendering a straight line for like 100ms and then reanimating it on a tab change").** Per-frame probing of the chart path and reveal clip under 6x CPU throttling (phone-like) found two causes:
  - The chart mounted in its "ready" phase, so one fully drawn frame painted before the reveal effect reset the clip to 0 and drew it again. `use-chart-phase-orchestrator.ts` now starts a ready chart already in "revealing", so the first painted frame is the empty clip.
  - The placeholder line appeared after 0.4 s, and loading the chart code on a throttled CPU took about 0.6–0.9 s. The delay is now 1.5 s, so the placeholder shows only on genuinely slow loads.
  - After the fix, probes show the first chart frame at clip width 0 and the placeholder never visible. 7/7 Chrome checks. The temporary probe spec was deleted.
- **Biggest remaining delay (not code):** Render's free plan sleeps after about 15 idle minutes, so the first visit waits roughly 30–60 s, and Neon's free compute also suspends. The fix is a paid instance (about $7/month) or an external keep-warm ping. That is the user's decision and has not been done.
- Verification: 93 Django tests OK (4 PG-only skipped); 6/6 Chrome checks (the chart check now requires the real chart and no skeleton, and Settings checks the manifest), including the no-JavaScript journeys.

## Categories and rules — September 25 (night, latest)

Why: the user said "continue with the features". The agreed order is custom categories, then limits, then notifications.

Implemented (milestone 4, first part):
- **Categories** (`Category`, migration 0006). Categories belong to one workspace. Each new workspace gets ten standard ones (Groceries, Dining, Housing, Utilities, Transport, Shopping, Health, Entertainment, Subscriptions, Travel), and the migration seeds existing workspaces. Names are unique per workspace, case-insensitive, and backed by a database constraint.
- **Managing categories.** Any workspace member can add, rename or archive them (Overview → Manage categories). Archiving hides a category from pickers, keeps it on past transactions, and turns off its rules. The foreign key is `RESTRICT`: a category still used by history can't be deleted, but deleting a workspace or user still cascades.
- **Setting a category.** The transaction Edit page has a Category field (this workspace's active categories; empty means Uncategorized). It is saved in the per-workspace overlay, so the original entry never changes.
- **Where categories show.** Overview has a **By category** list for the period: net of refunds, transfers excluded, largest first, with a proportional bar. Each row opens the Timeline filtered to that category. The Timeline has a Category filter (including Uncategorized), rows show their category, and the CSV export has a Category column.
- **Rules** (`Rule`, `budget/rules.py`, migration 0007). "Name contains" or "Name is exactly", matched against the original description after trimming, collapsing spaces and Unicode case folding. Any member can manage rules (Categories → Rules).
- **Rule order:** a category picked by hand (`category_source="manual"`, including a manual Uncategorized) wins. Otherwise the first enabled rule by priority, then by rule ID. Otherwise Uncategorized. Categories set before rules existed were marked manual by the migration.
- **When rules apply.** New and edited manual transactions get the current rules of every workspace that can see the account. Saving a rule offers **Preview matches** (a count plus the newest 20; nothing is saved) and an opt-in **Also apply to existing transactions**, which keeps manual choices.
- Not yet: rules re-running when an account is newly shared (only new or edited transactions and explicit backfill apply them), deleting a rule (turn it off instead), a bank-category mapping (waits for Plaid), splits, and budgets/limits.
- Verification: 108 Django tests OK (4 PG-only skipped), including new `test_categories.py` (9) and `test_rules.py` (6); `check` and migration drift clean; 7/7 Chrome checks, including a new `categories.spec.ts` (categorize → Overview → filtered Timeline → add a category → rule preview and backfill). Light and dark 360 px screenshots reviewed.

## Budgets and in-app alerts — September 25 (night, latest)

Why: the user asked to "continue with the other features" after the chart fix. The agreed order is limits, then notifications.

Budgets (`Budget`, migration 0008; `reporting.budget_progress`):
- A positive USD limit, monthly or yearly with no rollover, targeting **one** category or **one** name match (contains, same normalization as rules). Both rules are enforced by database check constraints and the form.
- Any member can manage budgets (Overview → Manage budgets); a Delete button sits on the edit page.
- Only posted spending counts: expenses minus refunds; transfers never count. Pending shows separately as an estimate. The limit is inclusive: $100 of $100 is not over, $100.01 is.
- In a group, only accounts shared there count.
- Overview shows a **Budgets** card: spent of limit, a bar (danger color when over), and left or over. The month view shows monthly budgets for that month plus yearly budgets for its year; the year view shows yearly budgets only.

In-app alerts (`BudgetAlert`, migration 0009; `budget/notifications.py`):
- When a budget's **current** period goes over its limit, each recipient gets one alert: the owner for personal budgets, the owner plus members for groups.
- A unique `(budget, recipient, period_start)` constraint plus `ignore_conflicts` make repeated or concurrent evaluations no-ops. A refund followed by another crossing does not alert again, and a new month or year can alert again.
- Closed periods are never evaluated, so backdated edits change reports but send no old alerts.
- Baselines: creating or editing a budget that is already over, or joining a group whose budget is already over, records a **silent** row. The first alert is then a real crossing.
- Budgets are evaluated after:
  - manual transaction saves, in every workspace that sees the account
  - transaction edits made in a workspace
  - rule saves
  - sharing changes
  - budget saves (as a baseline)
  - new members joining (as a baseline)
- Alerts store no amounts. The **Alerts** page (bell in the header, which shows "N new alerts" while any are unread) recomputes spent/limit from what the viewer can see now. Opening it marks alerts read. Alerts disappear if the viewer loses access to that workspace.
- Not yet: phone push (needs a service worker and VAPID keys) and email (needs an email provider, which is the user's decision). There is also no PostgreSQL concurrent-worker test for alerts yet; the unique constraint is the guarantee.

Verification: 118 Django tests OK (4 PG-only skipped), including new `test_budgets.py` (5) and `test_notifications.py` (5); `check` and migration drift clean; 7/7 Chrome checks (the categories spec now also covers an over-budget card and a real crossing → header alert → inbox → marked read). Light and dark budget-card and alerts-page screenshots reviewed. The spec now waits for the page crossfade before screenshots.

## Categorize by example — September 25 (night, latest)

Why: the user asked to "choose from the transactions, search from those by keyword, and when selected... detect that certain transactions with that name/description will automatically add/subtract into that category's limit". They chose **both entry points** and **"use my search word"** as the matching rule.

Implemented (no new model or migration; built on rules, budgets and alerts):
- **From a category** (category edit page → **Add transactions**, or the Timeline's "Add transactions to <category>" chip when filtered by a category): `views.category_add`, `category_add.html`.
  - Searching lists this workspace's visible transactions whose original description contains the keyword. It uses the same normalization as rules, so the list is exactly what the rule will catch; newest 100 shown, with the total.
  - Rows start ticked. Rows set by hand to another category start unticked and are labeled.
  - Saving puts ticked rows in the category as manual choices. With **Future transactions containing this go to <category>** (on by default, keyword editable), it creates a "name contains" rule once (`rules.ensure_rule` skips an equivalent rule). Unticked rows stay unchanged.
  - Forged or non-matching ids are ignored. Any member may do it, since it only writes this workspace's overlay. In a group, only shared accounts are listed.
- **From one transaction** (Edit page): **Also put other transactions with this name in this category, now and in the future**, with an editable **Name contains** field.
  - The field is prefilled by `rules.suggest_keyword`, which drops words starting with # or made of at least half digits and keeps three words. For example, "STARBUCKS #12 SEATTLE WA 98101" becomes "STARBUCKS SEATTLE WA", while "7-ELEVEN" stays.
  - Saving creates the rule and backfills: other matching rows get the category as rule choices, and rows set by hand elsewhere are kept.
- **Budget effect:** after either flow, the budgets are evaluated, so a category budget counts these rows and future matches immediately. A crossing alerts as usual.
- Verification: 124 Django tests OK (4 PG-only skipped), including new `test_categorize_by_example.py` (6); migration drift clean; 7/7 Chrome checks. The categories journey now also covers search → tick → keyword rule, and "also similar" on a transaction; its timeout was raised to 90 s. Light and dark 360 px screenshots reviewed.

## Budget types, disposable income and splits — September 25 (night, latest)

Why: the user said "push and go". After pushing, work continued with the next requested features: the budgeting framework and split transactions (spec "Requested additions — 2026-09-25").

Budget types (`Budget.kind`, `Budget.due_day`, `Workspace.expected_income_cents`, migration 0010):
- **Fixed bill**: monthly, with the expected amount as the limit and an optional due day (1–31). It shows "Paid" once posted spending reaches the amount.
- **Yearly or irregular cost**: a yearly total, shown as a monthly set-aside of ÷12 plus the amount set aside by now (total × month ÷ 12, so December equals the total).
- **Flexible spending**: the earlier behavior, monthly or yearly.
- The type fixes the period in the form (fixed = monthly, yearly = yearly). Only fixed bills keep a due day. A blank type means flexible, so older budgets and forms keep working.
- **Monthly plan (estimate)** on Budgets (`reporting.disposable`):
  - income − fixed bills − yearly set-asides = **disposable income**
  - then flexible budgets (yearly ones as a twelfth) are subtracted, giving "not planned yet", or a red warning when they exceed it
  - Income is the amount entered under Budgets → Income. Blank means the average posted income of the three complete months before this one, with pending excluded.

Splits (`SplitLine`, migration 0011; `SplitForm`; `views.transaction_split`; `reporting.category_totals`):
- The transaction Edit page has **Split across categories**: up to four lines of category and amount. There must be at least two lines, each category used once, all from this workspace's categories, adding up to the exact cent. An error says how much is left or over.
- A split applies to this workspace only, and the original entry is unchanged. Remove split restores the single category. Only the account owner can split, the same as other transaction edits.
- Each line takes the parent's classification and status: a refund split reduces each category, and a pending split is an estimate.
- `category_totals` is one grouped query for unsplit rows plus one for split lines. The Overview By category list and category budgets both use it, so they agree.
- The Timeline category filter lists a split row under each of its lines' categories, not under its old single category. Uncategorized excludes split rows.
- Rows show "Split: Groceries $30.00, Shopping $20.00", and the CSV Category column reads "Split: Groceries 30.00; Shopping 20.00".
- Name-match budgets still count whole transactions.
- Not yet: rule split templates such as 70/30 with largest-remainder rounding (spec default).

Verification:
- 134 Django tests OK on SQLite (4 PG-only skipped), including new `test_budget_kinds.py` (5) and `test_splits.py` (5).
- The new feature modules plus the concurrency tests pass on Neon PostgreSQL: 45/45 in 79 s.
- `check` and migration drift clean.
- 8/8 Chrome checks. The new `budgets.spec.ts` covers income, a fixed bill, a yearly cost, the plan card, and a split with the "left to split" error.
- Light and dark screenshots reviewed.

## Rule split templates and phone push — September 25 (night, latest)

Why: the user said "ok continue on the list". The next items were rule split templates, then phone push.

Rule split templates (`Rule.split_category`, `Rule.split_percent`, `SplitLine.from_rule`, migration 0012; `rules.largest_remainder`):
- A rule can split what it matches: the first category gets (100 − p)% and **Split with** gets p% (1–99, a different category). For example, "COSTCO → Groceries 70% / Shopping 30%".
- Amounts use largest-remainder rounding, so the lines always add up exactly: $10.01 at 70/30 gives $7.01 + $3.00. This is checked for every total from 1¢ to $3.99.
- `categorize` rewrites only rule-made lines. A hand-made split, or a category picked by hand, counts as a manual choice and is never touched; picking a category by hand also drops a rule split. Changing the rule to no split removes its lines on the next application.
- Archiving either category turns the rule off.
- Two-way splits only, marked `ponytail:` in the model (a lines table would be the upgrade).

Phone push (`PushSubscription`, migration 0013; `budget/push.py`; `assets/push.ts`; `/sw.js`; `manage.py vapid_keys`; new dependency `pywebpush` 2.5.0 with pinned transitive packages):
- **Settings → Notifications → Turn on for this device** asks for browser permission only on that tap. It then registers `/sw.js` and saves the subscription.
  - **Turn off** removes it from the server and the browser.
  - On iPhone it works once Budget is added to the Home Screen; the page says so.
  - The section stays hidden without JavaScript, push support, or server keys.
- Security:
  - Subscription endpoints must be HTTPS on a known push service (FCM, Mozilla, Apple, Windows). This SSRF guard rejects metadata IPs and look-alike URLs.
  - Unsubscribing only removes the signed-in user's own device.
  - The service worker has **no fetch handler**, so no page or financial data is ever cached.
- Delivery:
  - Only a *new, non-silent* budget crossing pushes: after commit, once per subscribed device of each new recipient.
  - The text is generic ("A budget went over its limit. Open Budget to see which one.") and opens Alerts. Lock screens never show names or amounts.
  - Every push uses the tag `budget-alert`, so a rare concurrent double send shows as one notification.
  - Devices reported gone (404/410) are deleted; other failures are logged.
  - Sending is inline with a 5 s timeout per device, marked `ponytail:` (move to a worker queue later).
- **Push is off until the owner sets both keys in Render** (see the operations guide). The browser test server generates throwaway keys per run.
- Not verified end to end: Chrome under Playwright refuses push subscriptions ("Registration failed - permission denied" even with the push permission granted through DevTools). The first real delivery check is on the owner's phone after the keys are set. The server side is covered by mocked tests, and the key format was verified to sign VAPID headers.

Verification:
- 144 Django tests OK on SQLite (4 PG-only skipped), including new `test_rule_splits.py` (5) and `test_push.py` (5).
- Push, alerts and splits 20/20 on Neon PostgreSQL.
- Migration drift clean.
- 8/8 Chrome checks. Budgets covers a 70/30 split rule; Settings covers the Notifications section and a push-only `/sw.js`.
- Initial JS 1.22 kB gzip; the push chunk is 0.87 kB and loads only on Settings.

## CSV import — September 28

Why: the docs listed CSV import as next, and it was the last open part of milestone 2. The user said "look at the md files and continue with what is supposed to be next".

What it does (`budget/imports.py`, `ImportBatch` and `Transaction.import_batch`/`source_row` in migration 0014, `ImportUploadForm`/`ImportMappingForm`, views `account_import`, `import_preview`, `import_undo`, template `import_preview.html`):
- **Account → Import CSV** (owner only; a group member or outsider gets 404) → upload → **Check file.csv**.
  - The preview page picks columns by name (date, description, amount or money out, an optional money-in column, an optional category) and guesses whether the file has a header row.
  - The sign convention is explicit ("Money out is negative (banks)" or "positive (cards)"). The default is whichever sign most amounts have. Money in counts as income, refund or transfer.
  - The page shows the first 20 rows, money in marked with a +, and totals. Nothing is saved until **Import N transactions**.
- **All or nothing:** a bad date, a non-number, NaN/Infinity, a fraction of a cent, $10bn or more, or both in/out filled lists the problem rows ("Row 4: …", spreadsheet row numbers) and saves nothing. Rows with no amount are left out and counted.
- **Duplicates:**
  - The same file (SHA-256) imports into an account once. This is enforced by a database constraint on finished imports, plus a locked preview row, so double-clicking Import saves one set.
  - Rows with the same date, amount and name as ones already in the account are flagged, matched one for one. Two real $4.50 coffees stay two when only one is already there. Flagged rows are left out unless ticked.
  - Identical rows inside one file are always imported.
- **Imported rows are read-only:** the original entry shows date, amount, description and pending as disabled, and posted changes are ignored. Only the type can change, and the link reads "Edit type". Workspace names, categories, notes and splits work as for manual rows.
- After an import, rules run in every workspace that can see the account. A category column counts as a hand choice, in the workspace the import started from; unknown names are left to rules. Budgets are re-evaluated, so alerts and phone push fire as for manual entries.
- **Imports** on the account page lists finished files with **Undo import**, which removes that file's transactions with their notes and splits.
- Unfinished previews keep the file's text only until imported, cancelled or a day old; they are deleted on the next upload to that account.
- Limits, marked `ponytail:`:
  - 1 MB and 5,000 rows per file, processed during the request; the milestone 3 worker jobs are the upgrade.
  - Comma-separated only.
  - US and ISO dates only (a DD/MM format picker if one shows up).
- Known gap: a checking account's card payment imports as money out (an expense) unless its type is changed. Rules only set categories today.
- Selects now leave room for the arrow, so long options no longer run into it (app-wide CSS fix).

Verification:
- 157 Django tests OK on SQLite (4 PG-only skipped), including new `test_imports.py` (13). The tests failed first.
- Imports, rules, alerts and concurrency 28/28 on Neon PostgreSQL.
- `check` and migration drift clean.
- 9/9 Chrome checks. New `imports.spec.ts`: upload, sign flip, preview, import, read-only amount, Timeline, undo. Light and dark 360 px screenshots reviewed.

## Email alerts — September 28

Why: the user asked for "email alerts, optional to turn on or off, defaulting to off, and with unsubscribe option".

What it does (`User.email_alerts`, migration 0015; `account_mail.email_budget_alert` and `unsubscribe_url`; views `email_alerts` and `email_unsubscribe`; `notifications.deliver`; `SITE_URL` setting):
- **Settings → Notifications → Email alerts** is off by default.
  - Turning it on needs a verified email; without one the card says to verify first.
  - The same card holds the phone push controls ("This device") when push keys exist.
  - The card says when the server has no email provider yet (console backend), so alerts only reach the log.
- **Sending:**
  - Only real, new budget crossings are sent, the same ones that push; silent baselines and repeats in the same period send nothing.
  - One email per person per evaluation, however many budgets crossed at once (push is now sent the same way).
  - Mail goes to the verified address after the database commit.
  - The text is generic ("A budget went over its limit. Sign in to see which one" + the Alerts link). No budget names, amounts, people or workspaces reach the mailbox or the mail provider.
- **Unsubscribe:**
  - Every email has an unsubscribe link and the `List-Unsubscribe` / `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers (RFC 8058, which Gmail and Yahoo expect).
  - The link is signed and never expires; all it can do is turn email alerts off. It needs no sign-in.
  - Opening it (GET) only asks. Link scanners open links, so the change happens on POST.
  - POST is CSRF-exempt, because mail apps' one-click unsubscribe posts without a token; the signature is the proof. A forged or altered token gets 404.
  - Turning emails back on is only possible from Settings.
- Links in these emails use `SITE_URL`, then Render's automatic `RENDER_EXTERNAL_URL`, then `http://localhost:8000`.
- Sending is inline after commit, marked `ponytail:` (move to a worker queue later). Mail failures are logged and never undo the alert.

Verification:
- 163 Django tests OK on SQLite (4 PG-only skipped), including new `test_email_alerts.py` (6). The tests failed first.
- Email alerts, push and notifications 16/16 on Neon PostgreSQL.
- `check` and migration drift clean.
- 9/9 Chrome checks; Settings checks "Email alerts · Off". The 320–390 px screenshot was reviewed.

**Owner action to actually deliver email:** pick a provider and set its SMTP values in Render (see the operations guide). Until then alerts are written to the Render log, like invitation emails.

## Plaid sandbox, slice 1 — September 28

Why: the user created a free Plaid sandbox account. Plan approved: connect a bank, choose accounts, sync inside the request. Render's free plan has no worker or cron, so automatic sync comes in slice 2, by webhook.

What it does:
- **Code:**
  - `budget/plaid.py`, the only module that imports the Plaid SDK
  - `BankConnection`; `Account.connection`, `provider_account_id` and `mask`; `Transaction.provider_id` and `provider_category` (migration 0016)
  - views `bank_connect`, `bank_exchange`, `bank_accounts`, `bank_sync`, `bank_disconnect`; templates `bank_connect.html`, `bank_accounts.html`; `assets/plaid-link.ts`
  - new dependency `plaid-python` 44.0.0 with pinned `nulltype`, `python-dateutil` and `six`
- **Connect:** Settings → Add → **Connect a bank**, shown only when Plaid keys are set.
  - Plaid Link opens; Plaid's script loads only on that page, in a 0.56 kB lazy chunk. The sandbox hint is user_good / pass_good.
  - The public token is exchanged server-side. The access token is stored **encrypted** (Fernet, `PLAID_TOKEN_KEY`, kept outside the database) and never shown or logged.
  - **Choose accounts:** every account is ticked by default and each one starts private. Choosing more later refetches history, because the cursor had already passed those accounts.
- **Sync:** right after choosing accounts, and on **Sync now** (account page, Settings → Bank connections). One sync a minute per connection; this is the cooldown and the in-request lock, marked `ponytail:`.
  - All pages are fetched before anything is saved. The cursor and the changes commit together, so a failure mid-way changes nothing.
  - Plaid's "mutation during pagination" restarts from the committed cursor.
  - If another sync committed first, this one steps aside.
  - Added, modified and removed are applied idempotently.
  - A posted transaction that replaces a pending one takes over the pending row itself, so names, categories, notes and splits carry over and it counts once.
  - Skipped: accounts that weren't imported, non-USD rows, zero amounts.
- **Classification:** Plaid's positive amount is money out.
  - Plaid categories `TRANSFER_IN`, `TRANSFER_OUT` and `LOAN_PAYMENTS` are **transfers**, so card payments never count as spending. `INCOME` is income. Other money in is a refund.
  - Plaid's detailed category maps to the standard categories (groceries, dining, shopping, transport, travel, housing, utilities, health, entertainment). It applies only where no rule matches, and hand choices always win. (Removed 2026-09-29: categories start empty; see "Categories you fill yourself".)
- **After a sync:** rules run, data revisions bump, and budgets are evaluated, so alerts, push and email follow.
- Synced rows are read-only like CSV rows: date, amount and description can't change, only the type.
- **Disconnect** revokes the connection at Plaid when it can and keeps the accounts and history as plain accounts.
- **Errors:** only Plaid's error code is shown ("Last sync failed (CODE)"), never the payload. If `PLAID_TOKEN_KEY` changes, the bank must be connected again.
- The email-alert unsubscribe link now has no timestamp, so each person always gets the same link. The earlier version could differ from second to second, which made a test flaky.

Verification:
- 175 Django tests OK on SQLite (4 PG-only skipped), including new `test_plaid.py` (12) with synthetic Plaid responses: token at rest, owner-only, chooser, added/modified/removed, pending→posted, failure on page two, mutation restart, cooldown and concurrent commit, types and categories, budget alert, read-only, disconnect.
- Plaid, email alerts, rules and concurrency 28/28 on Neon PostgreSQL.
- `check` and migration drift clean.
- 9/9 Chrome checks. Initial JS 1.25 kB gzip.
- **Real Plaid sandbox run** (owner's keys, throwaway local database, counts only printed):
  - A link token was created, then public token → exchange; the stored token is encrypted. Plaid returned 16 accounts (checking, savings, credit, loans, investments).
  - First sync: 0 rows (not ready). Second: **48 transactions**, history complete: 30 expenses, 3 refunds (flights), 15 transfers (credit-card payments, account transfers, loan payments). 30 were categorized (Transport, Travel, Dining, Shopping, Utilities).
  - A resync added 0 with no duplicates. The sandbox Item was then removed.
  - Found and fixed: "history ready" now waits for `HISTORICAL_UPDATE_COMPLETE`. Plaid sends about 30 days first, so the page no longer claims the full history early.
  - Sandbox labels the Gusto payroll deposit a transfer (Plaid's category); change its type if it should count as income.
- **Plaid Link in a browser:** the link token and Plaid's window load, and sandbox sign-in (user_good) works. Automated Chrome stalls on Plaid's final account-consent Continue: no request leaves the window. So the owner clicked through by hand, and it worked end to end: "Synced: 390 transactions added or updated". Checked in the local test database:
  - 14 accounts imported, 390 rows, 390 distinct Plaid IDs, 0 same-day/amount/name repeats
  - two years of history (2024-09-30 to 2026-09-26)
  - 245 expenses, 24 refunds, 121 transfers; connection ok, history ready
  - Link asks for 730 days, which is why this is more than the 48 from the API-created sandbox Item.

## Plaid slice 2: automatic sync, reconnect, duplicate warning — September 28

Why: the user said "do it" to the next Plaid piece.

What it does (migration 0017: `BankConnection.institution_id` and `needs_sync`; `plaid.verify_webhook`, `handle_webhook`, `_claim`, `_sync_once`; views `plaid_webhook`, `bank_reconnect`, `bank_reconnected`; new dependency `PyJWT` 2.15.0):
- **Automatic sync by webhook** at `POST /plaid/webhook/`.
  - New connections register it automatically when `SITE_URL` (or Render's URL) is HTTPS. Local connections can't be reached, so they don't.
  - Verification: an ES256 JWT in `Plaid-Verification`, signed by Plaid's key (fetched by key ID and cached in-process, `ponytail:`), issued in the last 5 minutes, whose `request_body_sha256` matches the exact body (constant-time compare). Forged, tampered, stale, HS256 and unsigned requests get 400. An unknown Item gets 200 and is ignored.
  - The endpoint is CSRF-exempt, because Plaid has no token; the signature is the proof.
  - `SYNC_UPDATES_AVAILABLE` syncs inside the request, marked `ponytail:` (move to a worker queue). `ITEM` `ERROR` records the error code; `LOGIN_REPAIRED` clears it.
- **One sync at a time per connection, and no update is lost:**
  - A sync claims the connection and releases it when done. A crashed claim frees after 5 minutes.
  - A webhook that arrives mid-sync sets `needs_sync`, and the running sync goes round once more.
  - The manual Sync now cooldown (60 s) now counts from the last finished sync. Webhooks have no cooldown.
- **Reconnect:** when Plaid says the bank needs a new sign-in (`ITEM_LOGIN_REQUIRED`, `ACCESS_NOT_GRANTED`, or a changed token key), Settings and the account page show **Reconnect** instead of Sync now. Reconnect opens Plaid Link in update mode on the same connection, then clears the error and catches up. Accounts and history stay.
- **Duplicate warning:** the chooser stores Plaid's institution ID. When you already connected that bank, it says so, and accounts whose last four digits match one you already import are unticked with a note. They are never merged automatically; matching digits are only a hint.

Verification:
- 184 Django tests OK on SQLite (4 PG-only skipped), including new `test_plaid_webhooks.py` (9): signed sync, six refused forgeries, unknown Item, login required then repaired (Reconnect shown), an update during a running sync, crashed-claim recovery, webhook URL and update-mode link tokens, reconnect flow and owner-only, duplicate warning.
- Plaid and concurrency 25/25 on Neon PostgreSQL. `check` and migration drift clean.
- 9/9 Chrome checks.
- **Real sandbox:**
  - A sync after Plaid's `reset_login` returned `ITEM_LOGIN_REQUIRED`, so needs-reconnect is set.
  - An update-mode link token was issued.
  - The earlier sync and resync still hold: 48 rows, then 0.
- **Not verified:** real webhook delivery. Plaid can only reach the public HTTPS site, so the first real check is after the owner adds the Plaid keys in Render and connects a bank there.
- Deferred: 6-hour catch-up sync (needs a scheduler, a cost decision), retry/backoff, and handling of `PENDING_EXPIRATION`.

## Planning tools: net worth, recurring bills, goals — September 28

Why: the user said "don't need reports. i like goals, make them optional, add recurring bills, and net worth." They chose:
- goals off until turned on in Settings
- bill reminders 3 days before
- net worth from synced balances plus manual items

Wireframes came first (UX doc section 6b). Three commits, one per slice.

**Net worth** (migration 0018; `reporting.net_worth`; `plaid.record_balances`; views `net_worth_page`, `account_edit`):
- Each account keeps a last known balance and whether it counts as owned, owed or not at all.
- **Plaid:** every sync records the cached `/accounts/get` balances (no extra Plaid product). Credit and loan accounts count as owed. The first balance sets the kind; after that the owner's choice sticks. A balance failure never fails a sync.
- **Manual:** a home, a car or a loan is an account with a typed value (Add something you own / owe, or Edit on the account). A synced balance can't be typed over.
- Net worth = own − owe over the accounts visible in the workspace, so a group counts only shared accounts. It shows as an Overview card and a page labeled an estimate, not advice. "Not counted" is collapsed.
- Real sandbox: all 14 test accounts got balances, 8 owned and 6 owed.

**Recurring bills** (migration 0019: `Recurring`, `BillReminder`; `budget/recurring.py`; views `bills`, `bill_edit`, `bill_delete`, `daily_tasks`; `.github/workflows/daily.yml`):
- **Found in your transactions:**
  - Series in visible posted spending or income, grouped by the bank name without store numbers, at least 3 times.
  - A weekly, monthly or yearly gap, where a skipped period still counts.
  - Every amount within 10% of the usual one, and still going (the last one within 2 periods).
  - **Confirm** or **Not recurring**. The server recomputes the series, so posted amounts are never trusted. A dismissed series isn't suggested again.
- Or add one by hand. A typed name is kept whole, so "Car payment 1" and "Car payment 2" stay separate. The browser test caught the first version merging them.
- Due dates step from one known date, and month ends clamp (Jan 31 → Feb 28 → Mar 31).
- **Next 30 days (estimate):** bills, income and "left after bills". It never counts as spending. The Budgets page shows the next three.
- **Reminders:**
  - From 3 days before each due date, once per person, bill and date, for everyone in the workspace.
  - In the app: Alerts → "Bill due Oct 1: Rent", shown in the unread count.
  - Push and email say only "A bill is due soon", and email follows the person's email-alert setting.
  - Checked on Overview and Alerts, after every bank sync, and by the daily task.
- **Daily task:** `POST /tasks/daily/` with `Authorization: Bearer $TASKS_TOKEN` (404 when unset or wrong). It runs reminders plus a **catch-up bank sync** for connections quiet for 6 hours.
  - A scheduled GitHub Action calls it once a day and skips itself until the secrets exist. It's free.
- Real sandbox data: the Bills page found SparkFun, McDonald's, Starbucks and others as monthly series.

**Goals** (migration 0020: `User.goals_enabled`, `Goal`; `budget/goals.py`; views `goals_toggle`, `goal_list`, `goal_edit`, `goal_delete`):
- Off by default, per person: Settings → Goals → Turn on. When off, every goal page is 404 and no goal UI shows; turning off deletes nothing.
- **Save up** or **Pay off a debt**, with a target, an optional date and an optional linked account.
  - Savings follow the account's balance.
  - A debt follows how much its balance dropped since the goal was set.
  - Without a link, the typed "saved or paid so far" counts.
  - A linked account that stops being visible in the workspace falls back to the typed amount; a group can't link a private account.
- The monthly amount needed is `ceil(remaining / months left)`. A passed date asks for the rest now and says so.
- Budgets shows up to three goals; the Goals page shows all of them.

Verification:
- 203 Django tests OK on SQLite (4 PG-only skipped), including new `test_net_worth.py` (5), `test_recurring.py` (10) and `test_goals.py` (4).
- New modules plus concurrency 22/22 on Neon PostgreSQL. `check` and migration drift clean.
- 10/10 Chrome checks. New `planning.spec.ts`: a manual home in net worth, a bill in the forecast and in Alerts, goals turned on, added, shown at 25% on Budgets, then turned off again. Light and dark 360 px screenshots reviewed.

Owner actions for the daily task (optional, free):
- Pick a long random value.
- Add it as `TASKS_TOKEN` in Render.
- In GitHub → Settings → Secrets → Actions, add `TASKS_TOKEN` (same value) and `SITE_URL` (the site's https address).

## Timeline by account: tick boxes and Side by side — September 28

Renamed later the same day: the layouts are **Graph | List**; "Side by side" in this section means List.

Why: the user wanted a per-account view: all accounts together, or ticked ones. A second layout lists each account side by side, with money moving between them drawn and toggleable. Their choices: on the Timeline page; lines only between their own accounts. Wireframe: UX section 3b; rules: spec "Requested — 2026-09-28".

**Direction** (migration 0021):
- `Transaction.money_in` records which way the bank moved the money.
- Plaid sets it from the sign, CSV from the sign mapping. By hand, Type offers "Transfer out or card payment" and "Transfer in"; bank rows keep the bank's direction.
- The backfill for older rows:
  - income and refunds are in
  - a transfer is in when it's `TRANSFER_IN…`, a CSV row, or a `LOAN_PAYMENTS…` row on a liability account
  - everything else is out

**Tick boxes:**
- The Timeline's account filter is now tick boxes, in a collapsed "Accounts · 2 of 14" panel above Filters; none ticked means all.
- They join the Filters form with the `form` attribute, so dates, search and CSV export keep working. The Filters panel opens only for its own filters.

**Side by side** (`?view=lanes`; `budget/flows.py`, `lane_context` in views, `components/lanes.html`):
- **Lanes:**
  - one lane per ticked account, or per account with rows in the range
  - date bands across every lane, newest first, at most 400 rows, never a partial day
  - lane headers show money in and out for the range
  - the lanes scroll both ways inside their own box: sticky lane names, sticky dates
- **`flows.pair`:**
  - transfers only (the workspace's type), one for one
  - the same amount, opposite directions, another account, at most 5 days apart; the closest date wins
  - candidates are the visible transfers from 5 days before the range to 5 days after, so a private account is never a partner and shows as "elsewhere"
- **Row text:** every transfer says "To Savings ••1111", "From Checking ••0000, Sep 10" or "To elsewhere".
- **`assets/flows.ts`** (a lazy 1.5 kB chunk) draws one SVG that's hidden from screen readers:
  - curves with arrowheads between pairs; dashed when pending
  - a short stub ending in a small circle for elsewhere, so it never looks aimed at the next lane
  - hover or focus lights up both sides
  - draw-in unless reduced motion is on; redraws on resize
  - Show money moving hides the lines and is remembered in the browser; storage failures are ignored
- Synced account names already carry their mask ("Plaid Checking ••0000"), so the view never adds it again.

Verification:
- 213 Django tests OK on SQLite (4 PG-only skipped), including new `test_flows.py` (10). `check` and migration drift clean; flows, Timeline and import tests 27/27 on Neon PostgreSQL.
- 11/11 Chrome checks. The new `lanes.spec.ts`: two accounts, transfer out and in by hand, ticked, Side by side, one line and one stub drawn, lanes scroll inside their box at 360 px, and the toggle survives a reload. Light, dark and desktop screenshots reviewed.
- `imports.spec.ts` now searches for its own row: the shared test user has over 50 rows this month.
- The real sandbox rows in the local test database give 121 transfers and 0 pairs. That's expected: each sandbox account's transfers stand alone. For example, the card's $2,078.50 autopay has no matching checking row.

## Compact Timeline controls and the Overview Chart | Budgets switch — September 28

Why: the user wanted the frontend more compact. They chose to remove the Overview Budgets card, and to count monthly budgets × 12 in the Year view. Wireframes: UX §2 and §3b.

**Timeline:**
- **⋯ menu:** a native `popover` (`#timeline-menu`) holds Export CSV and, in Side by side, Show money moving.
  - Placed under the button by `app.tsx` in page coordinates, so it scrolls with the button. Escape and outside taps close it.
  - A 150 ms scale and fade from the corner (`@starting-style`); without JS the browser centres it.
- **Filters:**
  - The toggle is a disclosure button (`aria-expanded`) on the same row as Graph | List.
  - The `js` class set before the page draws hides the panel, so nothing flashes. Without JS the panel is open and the button hidden.
  - The fields are 2 across on a phone and 4 on a desktop (Search takes 2).
  - The account tick boxes moved inside the form (no `form=` attribute any more), with **Select all / Clear all** and a live "N of M" count.

**Overview:**
- A small **Chart | Budgets** segmented switch on the top card.
  - The choice is saved in `localStorage` and applied before the page draws (a `data-overview` attribute from `base.html`), so the other panel never flashes. Without JS the budget list shows.
  - The chart mounts only when its panel is first shown.
- The separate Budgets card is gone. "Manage budgets ›" stays visible under both views, since it's the way to the Budgets page.
- Each budget row: name (· fixed, · year for a yearly budget in a month), then "left", "to go", "Paid" or "over" in the danger colour. A bar shows "$X of $Y", with pending.
- The total line covers only budgets measured over the period shown, so a yearly budget stays out of a month's total: spent of limit · left · over.
- `budget_progress(..., span=)`: in the Year view a monthly budget uses the whole year and 12 times its limit, and every result carries `limit_cents`. Alerts and the Budgets page call it unchanged.

Owner review in the local preview found three things, all fixed:
- The column header strip broke at each gutter. Each head now also covers the gutter after it.
- Lane rows drew over the bottom menu. The bottom nav now has `z-index: 40`, and `.lanes` isolates its own layering.
- The layout buttons are renamed **Graph | List**.

Verification:
- 215 Django tests OK (new: the year view counts 12 times and totals follow the period; the menu and accounts sit inside Filters).
- 11/11 Chrome checks, with specs updated for the new controls; `budgets.spec.ts` checks the switch survives a reload.
- Screenshots reviewed: phone filters, desktop menu, Overview Budgets in light and dark.

## Savings page and demo data — September 28

Why: the user asked to see savings and how much is in savings accounts, and how savings → checking → spending is tracked. They chose automatic marking plus a switch, and a page reached from an Overview card. Wireframe: UX §6c.

**The rule:** a transfer lowers the savings balance but is never spending. Spending rises only when the money is spent from checking, so nothing is counted twice.

**Savings page:**
- `Account.is_savings` (migration 0022): null until decided.
  - `bank_accounts` sets it from the Plaid subtype (`plaid.SAVINGS_SUBTYPES`: savings, money market, cd); `record_balances` fills it only while null.
  - The Edit page has a "Savings account" switch (`AccountForm`), and the owner's choice sticks.
- `reporting.savings(user, workspace, start, end)`:
  - visible savings accounts, posted rows, by `money_in`: in, out and net per account, per day and, for a year, per month
  - `cumulative_cents` is the net saved so far; the balance is the sum of known balances
- `savings_page` (`workspaces/<id>/savings/?period=`): the hero, change against the previous period, the chart (`spending-chart.tsx` now takes tooltip labels from `data-total-label` / `data-day-label`), Month/Year, In/Out/Net, a Year table, accounts, and "View savings transactions" (the Timeline List view with the savings accounts ticked).
- The Overview card shows only when there are savings accounts.

**Overview Spending | Savings switch** (the user's follow-up: "make it toggleable between savings and spending"):
- The top card flips in place. The separate Overview Savings card is gone.
- A generic `[data-switch]` handler in `app.tsx` serves both Overview switches. `base.html` applies the saved `overview` / `overviewMode` choices before the page draws, and CSS shows the matching `[data-panel]` / `[data-mode]` panels.
- Charts: several per page (`data-series`), each mounted once visible.
- The workspace view adds the savings change, `savings_timeline()` and `savings_series`.

**Demo data:**
- `tests/browser/seed_demo.py [--reset]` fills the preview's `browser-check` user in `.local/browser.sqlite3` with made-up data.
- Eight "Demo" accounts: checking, savings, high-yield, brokerage, a home estimate, a card, a car loan and a cash wallet.
- About 250 transactions over six months:
  - payroll, rent, utilities, card spending by category, subscriptions, a refund, two pending
  - interest
  - paired transfers: checking → savings, savings → high-yield, sometimes savings → checking, card and loan payments, a brokerage contribution, an ATM withdrawal
- Five budgets are added when missing.
- It refuses to run twice without `--reset`. Synced sandbox accounts are marked as savings on their next Sync now.

Verification:
- 220 Django tests OK, including new `test_savings.py` (5); savings, budgets and net worth 16/16 on Neon PostgreSQL. Migration drift clean.
- 12/12 Chrome checks, with new `savings.spec.ts`: a manual savings account with a transfer in and out, the Overview card, the page, the chart and the Timeline link. Light and dark 360 px screenshots of the Month and Year views reviewed.

## Spending | Savings in the header, on Overview and Timeline — September 28

Why: the user's sketch:
- switch between Spending and Savings on both tabs
- drop the workspace name that repeats the selector
- put the switch beside the selector, and Invite by the bell

User choices: the Timeline in Savings shows only savings accounts; the Overview hides By category in Savings; the Timeline's "‹ Personal" link goes too.

**Mode:**
- A `mode=savings` cookie; when it's missing, the mode is spending. The `[data-switch]` handler writes it for a fieldset with `data-cookie`.
- The server reads it:
  - `base.html` puts `data-overview-mode` on `<html>`, so CSS shows the right panels before paint. The localStorage copy is gone.
  - `views.savings_mode()` and `timeline_scope()`: in Savings, the Timeline and its CSV export use only `is_savings` accounts, and the tick boxes list only those.
- The Timeline's switch has `data-reload`: it reloads without `account`, `before` and `rev`.
- Every switch re-adds the speculation rules, so a tab prefetched in the old mode isn't served.

**Timeline Savings card:**
- `reporting.saved_daily(rows, start, end)` gives in, out, net and the running net per day: posted rows only, by `money_in`. `savings()` now uses it too.
- It feeds the hero, the "Saved so far" chart, Money in / Money out / Net saved and the daily table.
- The day headers show each day's net saved.

**Header (`base.html`):**
- Invite, or Manage sharing in a group, shows whenever a workspace is open. The username is hidden below `sm`.
- The workspace selector is a button with a native popover `nav.menu`, capped at `max-h-96` and scrollable.
- The shared menu code now aligns a left-side button's menu to the button's left edge.
- "Workspace:" is screen-reader-only on phones, so the selector and the switch share a row at 320–360 px.

**Overview:**
- The visible title row and the in-card switch are gone; an `sr-only` h1 keeps the page's heading.
- By category carries `data-mode="spending"`.

**Verification:**
- 221 Django tests OK. The new test covers the Timeline, the export, a group and the Overview under the cookie.
- Savings and flows 17/17 on Neon PostgreSQL.
- 12/12 Chrome checks. `savings.spec.ts` now switches in the header on the Overview, opens the Timeline in Savings, and switches both ways there.
- Screenshots reviewed: 360 px light and dark, the open workspace menu, and the desktop header against the sketch.

## 1M | 1Y | Lifetime, the (i) note and the header pill — September 28

Why: the user asked for:
- the phone switch right-aligned, with the selector at its height
- the Overview note behind an (i) popup on phones
- + and the bell in one pill
- a 1M, 1Y and Lifetime selector on the Timeline and the Overview

User choices: calendar month and year; a people icon for Manage sharing in groups.

**Reporting:**
- `daily()` and `saved_daily()` take `by_month`: they group by `TruncMonth` and zero-fill the first of each month.
- `monthly()` is gone. `savings()` now builds `months` with it too, which fixes multi-year ranges (it used to assume one year through `ExtractMonth`).
- `by_year()` sums a monthly series per year; `first_day()` gives Lifetime's start.

**Overview and Savings page:**
- `period()` accepts `all`.
- `period_context()` replaces the period code the two views duplicated: label, prev and next, `prev_range`, the chip targets (`periods`) and `range_params` for Timeline links (`span=all` or start/end).
- Lifetime has no comparison and no arrows; the Budgets panel asks for 1M or 1Y, and the table shows per-year totals.
- `components/period_nav.html` is the shared `← 1M 1Y Lifetime →` nav.

**Timeline:**
- `TransactionFilterForm` has a hidden `span`. `span=all` with no dates runs from the first transaction to today and skips `MAX_DAYS`.
- The view builds the `ranges` chips (1M and 1Y are the month and year of the range's end) and keeps the other filters.
- Past `MAX_DAYS` the series is by month. The list's day headers then come from a daily series over the page's own dates.
- `filtered` ignores start, end and span, and Clear filters keeps the range.
- In `lane_context`, transfer candidates start at the oldest lane row.

**(i) note:**
- The same `<p popover class="tip">` shows inline from `sm` up (CSS overrides the popover UA styles) and is an auto popover on phones, placed full width under the (i) by the shared popover code.
- It closes on outside taps and Escape, and when focus leaves the (i). On close its inline placement is cleared, so a wider screen shows it inline again.

**Header:** `.icon-pill` holds + (or the people icon) and the bell. The row 2 container is `max-sm:justify-between`, and the selector is `min-h-10`.

**Verification:**
- 222 Django tests OK (new: by-month across years; Lifetime Overview, Timeline and Savings page; chips aren't filters). 48/48 savings, flows, reporting and budgets tests on Neon PostgreSQL.
- 13/13 Chrome checks, with new `ranges.spec.ts`: the phone (i) opens and closes, Lifetime on the Overview, the note inline at 1280 px, and the Timeline chips.
- Screenshots reviewed: phone light and dark, the open tip, desktop Lifetime.
- **Found:** the reused `.local/browser.sqlite3` keeps every run's data (116 budgets under `browser-check`), and `budget_progress` runs one query per name-match budget, so the Overview takes 1–3 s there.
  - `transactions.spec.ts` now allows 60 s and waits for the URL after saving.
  - Load-gate item: batch the name-match budgets (done 2026-09-29, see "Snappier").

## One range bar, a smaller total and a Chart | Budgets icon — September 29

Why: the user asked, with a sketch, for:
- a smaller total that fits $999,999,999.00
- Chart | Budgets as one icon on the total's line
- 1M / 1Y / Lifetime in the same place on the Overview and the Timeline
- a shorter chart and range selector

User choice: the range bar is the first row on both pages.

**Range bar:**
- `components/period_nav.html` takes `range_nav` from `views.range_nav(kind, prev, next, month, year, lifetime)`: hrefs, with arrows only for a month or a year.
- `period_context()` builds it for the Overview and the Savings page (`?period=…`).
- The Timeline builds it from its range: `month` or `year` when the range is exactly that calendar period, `all` for Lifetime, otherwise custom (no arrows, no current chip). Its arrows use `period_bounds()` either side and keep the other filters.
- It is the first row everywhere, in a `min-h-11` row, so it sits at the same height as the Timeline's ⋯ row. The Timeline `h1` is `sr-only`.

**Total:** `.hero-amount` is 1.75rem on phones and 2.5rem from `sm` up (was 3rem).

**Chart | Budgets:**
- The radio fieldset is now `button[data-overview-toggle]` (`.icon-toggle`). CSS shows the icon for the view it switches to; JS sets `aria-label` to "Show budgets" or "Show chart".
- `applySwitch()` is shared with the header switch, which is now the only `[data-switch]`, so its localStorage branch is gone.

**Chart:** `.chart-slot` and `AreaChart` are 2.8:1, capped at 13rem. The slot needs `width: 100%`; otherwise the height cap narrows an auto-width block with an aspect ratio.

**Verification:**
- 222 Django tests OK (Timeline arrows step a month and keep filters; custom ranges have none).
- 13/13 Chrome checks. `ranges.spec.ts` now covers:
  - "$999,999,999.00" on one line at 360 and 1280 px
  - the bar at the same y on the Overview and the Timeline
  - the Timeline ← step
- `categories.spec.ts` searches for its own row, because the reused preview database now pushes it off the first page.
- Screenshots reviewed: 360 px light and dark, and 1280 px.

## Range bar over the chart, and date labels — September 29

Why: the user asked for:
- the 1M / 1Y / Lifetime bar centered right above the graph, and shorter, on the Overview, the Timeline and the Savings page
- labels under the graph: the period start at the bottom left, and today or a way back to this period at the bottom right

User choices:
- the current period's chart ends at today
- a year is labelled `2026`, and Lifetime uses the first record's date
- in the List layout, the bar is centered above the list

**`views.range_nav(kind, start, end, prev, next, month, year, lifetime, this_period)`** now also returns:
- `left`: `M/YY` for a month, `YYYY` for a year, otherwise `M/D/YY`
- `right`: today, or a custom range's end
- `back`: an (href, "This month" / "This year") pair, when a month or year that isn't current is shown

`this_period` is `?period=…` on the Overview and the Savings page. On the Timeline it's the range link for `period_bounds(kind, today)`, which keeps the filters.

**Ending at today:** `until_today()` trims the chart series to today. On the Timeline only the chart JSON is trimmed (`chart_days`), because the totals are summed from `days`.

**Templates:**
- `components/period_nav.html` is `mx-auto w-fit`, `p-0.5`, with `text-xs py-0.5` segments and 28 px arrows.
- The new `components/chart_labels.html` goes under each chart.
- **Overview:** the bar is inside each mode section, so it's rendered twice and the hidden one is `display:none`.
- **Timeline:**
  - the dates line shares its row with ⋯
  - when there's no graph card, the bar is centered above the list
- The `AreaChart` bottom margin is 4.

**Verification:**
- 223 Django tests OK. New: labels for month, year and Lifetime; the current month ending at today; the `This month` and `This year` back links on the Overview and the Timeline.
- 13/13 Chrome checks. `ranges.spec.ts` checks:
  - the bar is centered above the chart on the Overview and the Timeline, and centered in List
  - `This month ›` returns to the current month
- Screenshots reviewed: phone light and dark, desktop, and the Savings page.

## Swipes, time markers and tabs that keep the range — September 29

Why: the user asked for:
- "Today" as plain text in place of the "This month" chip
- phone swipes: on the chart, away from its line, for the period; elsewhere for the tabs
- markers on the chart
- dropping "View … timeline", because switching tabs should keep the period

User choice: time lines.

**Tabs:**
- `tab_query` holds the query strings that `base.html` appends to the Overview and Timeline tabs.
- `period_context()` sets them on the Overview and the Savings page.
- On the Timeline: `?period=YYYY-MM`, `YYYY` or `all`, and none for a custom range; the Timeline tab keeps its own query.

**Markers:**
- `chart_markers(kind, series)` gives `{day, pct, label}` across the chart's x domain, from the series' first day to its last:
  - a month: the 8th, 15th and 22nd
  - a year: Apr, Jul and Oct
  - Lifetime: each Jan 1
  - Labels near the ends are dropped.
- The slots carry `data-markers`. `spending-chart.tsx` draws `TimeMarkers` (dashed `var(--chart-grid)` lines, using `xScale`), and `chart_labels.html` places the labels at `calc(4px + pct·(100% − 8px))`.

**Today:** `until_today()` leaves a period that hasn't started with its whole flat line, so a swipe into next month still shows a chart.

**Swipes (`assets/swipe.ts`):**
- It's loaded from `app.tsx` and is active below 640 px.
- **Chart swipes** use a capture-phase `touchstart` on each chart slot, which runs before the chart's React handlers.
  - A touch within 24 px of the line goes to the tooltip. The line is the longest stroked path with a transparent fill, sampled with `getPointAtLength` in screen coordinates.
  - Otherwise the swipe owns the touch and follows the visible Period arrow.
- **Page swipes** use a passive `touchstart` on the document, inside `main`.
  - They skip charts, form controls, popovers, sideways-scrolling ancestors and the 20 px screen edges.
  - They follow the next or previous `.nav-link`.
- **Motion:**
  - Both lock direction at 10 px, follow 1:1, rubber-band with no target, and commit past 25% of the width or on a flick (over 0.4 px/ms in the same direction).
  - Committing slides out with WAAPI. Motion isn't imported in `app.js`, so the entry doesn't load twice.
  - The next page enters from the side, via `sessionStorage.swipe`.
  - Back-forward cache restores cancel the slide-out. Reduced motion just navigates.
- `#main` has `touch-action: pan-y` on phones.

**Verification:**
- 223 Django tests OK. New: the marker days and pct, `Today`, the tab queries for a month, a year, Lifetime and a custom range, and the removed link.
- 14/14 Chrome checks, with a new `swipes.spec.ts` that uses CDP touch events:
  - a drag on the line keeps the page
  - a swipe on the empty chart goes to the next month and back
  - a swipe on the page goes to the Timeline and back, keeping the range
  - Settings stays put
- Screenshots reviewed.

## Budget tab, Settings in the header — September 29

Why: the user wanted budgets easier to see:
- a separate Budget page with every spending category, where you can create one, set a limit and choose what goes in it
- Settings in the top-right pill
- the Overview in the middle of the bottom bar

User choices:
- the tabs are Timeline · Overview · Budget
- the Overview's budget pieces move to the tab
- rows open a category page
- the plan, Goals and Bills sit below the categories

**Navigation:** `base.html` puts a gear (`aria-label="Settings"`) in `.icon-pill`. The bottom nav is Timeline, Overview and Budget. The Budget tab carries `tab_query.overview`, so it keeps the period. `swipe.ts` follows the nav order unchanged.

**Budget tab (`budget_list`):**
- `period_context()` supplies the period.
- `by_category()` gives each category's spend. `period_budgets()` (formerly inline on the Overview) runs `budget_progress()` and gives the limits; a category shows the budget whose period matches the view.
- `others` holds the name-based budgets.
- The categories route redirects back to the tab when the form posts `period`.

**Category page (`category_edit` → `category.html`):**
- It shows the spend, `limits`, the rules whose category or split category this is, and the last 10 rows. Those come through `TransactionFilterForm(category=…)`, the Timeline's own filter, then `labelled()`.
- Rename and archive post in place.
- `budget_edit` and `rule_edit` take `?category=` (`with_category()` prefill) and a same-site `?next=` (`next_url()`; anything else falls back).

**Overview:** the Chart | Budgets icon, the budgets panel, By category, and the Manage links are gone, along with their JS, CSS and `localStorage` flag. `workspace_detail` no longer runs `budget_progress` or `by_category`.

**Found and fixed:** some right swipes in the last push were Chrome's own history swipe, not `swipe.ts`: `touch-action` doesn't stop it. Phones now set `html { overscroll-behavior-x: none }`. `swipes.spec.ts` also waits for each page change's crossfade, because during it touches land on `<html>`.

**Verification:**
- 224 Django tests OK. New: the Budget tab lists every category, including ones with no spending, with limit and uncategorized rows; adding returns to the tab; the category page shows limits, rules and recent rows; the prefill; `next`, and the fallback for an outside `next`.
- 48/48 budgets, categories, reporting and savings tests on Neon.
- 14/14 Chrome checks. The budgets, categories, planning and swipe specs now go through the tab.
- Screenshots reviewed. The preview database has dozens of duplicate Housing budgets from past runs, which makes its category page long.

## Categories you fill yourself — September 29

Why: the user asked me to verify the category and limit logic against their flow, and several parts didn't match:
- bank sync pre-sorted by the bank's category
- no delete
- "Add transactions" needed a search and didn't name accounts
- silent moves
- no keyword picker

User choices: keep the starter categories with nothing sorted into them; delete uncategorizes; one move confirm on save; match on all chosen words.

**Rules (`rules.py`):**
- `categorize()` uses only the workspace's rules. `bank_category()` and `PLAID_CATEGORIES` are gone.
- Plaid's transfer, income and refund classification is unchanged.
- There's a new rule kind, `words` ("Name has all of"), with migration 0023: every word must appear, in any order.
- `ensure_rule(..., kind=)` and `suggest_keyword(..., limit=None)`.

**Picker (`category_add`):**
- **Step 1:**
  - It lists the newest 100 visible rows, and `?q=` narrows them the same way as before. `?uncategorized=on` shows only rows with no category and no split.
  - Each row shows its account (and owner in a group), and `place()` gives here, other, split or none.
  - A search ticks the matches that are free or already here; the full list starts unticked.
- **Step 2** runs when "also" is on (checked by default) or a chosen row is in another category or a split:
  - `name_words()` offers the ticked names' words as chips, with `suggest_keyword()` pre-checked.
  - "Update preview" counts the other matches.
  - Move / Leave radios cover the rows in other categories.
- **Save:**
  - The ticked rows, plus the word matches when "also" is on (minus the conflicts when you choose Leave), become manual here, and their split lines are removed.
  - "Also" adds a `words` rule, so future imports land here.
  - The posted ids are intersected with the visible rows.

**Delete (`category_delete`, POST):**
- It removes whole splits that used the category and clears annotations; both foreign keys are `RESTRICT`, so these come first.
- Then it deletes the category, which cascades its budgets and rules, and re-runs `evaluate()`.
- The UI is a `<details>` "Delete category…" at the bottom of the category page.

**Not changed:** a transaction's own edit page keeps its "Also put other transactions with this name…" option, unchecked, as a `contains` rule.

**Verification:**
- 226 Django tests OK. New:
  - the full list with account labels and places
  - the move prompt, both Move and Leave
  - the word chips, the rule and a later import landing in the category
  - the `words` matcher
  - delete: splits, rules, budgets, outsiders, and GET
  - Plaid: no category without a rule, and a sync alert through a rule
- 36/36 of the categorize, categories, budgets and Plaid tests on Neon.
- 14/14 Chrome checks. `categories.spec.ts` covers the account labels, the chips, saving and deleting a category.
- On the reused preview database, the first rule saved with "apply to existing" cleared 245 old bank-guessed categories. That is expected, so the browser check no longer expects exactly 0.

## Snappier — September 29

Why: the user said the app felt a little slow and asked me to look at every possibility.

Measured with Django's test client on a copy of the preview database (SQLite, this PC; the second of two loads). Render's free instance has a fraction of a CPU, so its times are several times longer. Query counts are exact; times are noisy.

| Page | Before | After |
|---|---|---|
| Overview | 120–290 ms, 31 queries | ~95 ms, 28 queries |
| Budget tab | 240–340 ms, 95 queries | ~80 ms, 20 queries |
| Alerts | 520–540 ms, 244 queries | ~55 ms, 14 queries |
| Timeline | 160–250 ms, 15 queries | unchanged (see below) |

**Changes:**
- **Pages are gzipped:** `GZipMiddleware` sits right after WhiteNoise, so only HTML is compressed (static files already were).
  - The Overview goes from 184 KB to about 10 KB over the network.
  - Django pads gzip output against BREACH, and CSRF tokens are masked per request.
- **Name budgets share one scan per period** (the load-gate item). `budget_progress()` collects each period's name patterns and matches them in one pass. Category budgets already shared `category_totals()`. Tested: three name budgets cost the access lookups plus one scan.
- **Alerts:**
  - One `budget_progress()` call per workspace and period instead of one per alert.
  - `recurring.remind()` runs only for workspaces that have bills with reminders. The preview user sits in 114 test-run groups.
  - Tested: six alerts cost the same number of queries as one.
- **Previous-period savings:** the Overview and Savings pages use `saved_net()`, one aggregate, instead of a whole `savings()` call.
- **`net_worth()`:** its "uncounted" list compared model instances in a loop (O(n²)); it now tests each account's fields.
- **Neon connections:** `CONN_MAX_AGE` goes from 60 to 600 s, with health checks still on, so an idle minute no longer costs a new TLS handshake.
- **Motion:**
  - The chart draws in over 350 ms, down from 600.
  - A page reached by a swipe enters over 250 ms, down from 350.
  - A page swipe now starts loading the next page at once; before, it waited for the 180 ms slide-out.

**Looked at and left alone:**
- **Timeline:** its time goes to rendering one Django form widget per account in Filters. The preview has 408 test accounts, while a real person has a handful.
- **Chart code:** 160 KB gzipped (React, Motion, visx). It is cached forever after the first visit, and replacing it would mean rewriting the Bklit charts.
- **Fonts and images:** fonts were already A/B tested, and the only images are the home-screen icons.
- **`no-store`:** it stays for privacy on shared phones, even though it means Back reloads from the server.
- **Eager tab prefetch:** kept; revisit at the load gate.
- **The biggest delay is still the free plan's cold start.** A free option is in the [operations guide](operations.md).

**Verification:**
- 228 Django tests OK
- 46/46 of the budgets, reporting, savings and notifications tests on Neon
- `npm.cmd run build`; 14/14 Chrome checks on a restarted preview server
- `curl` with `Accept-Encoding: gzip` returns `Content-Encoding: gzip` and `Vary: Accept-Encoding`

## Compact Timeline — September 29

Why: the user asked to compact the Timeline:
- remove the text above the graph
- move the ⋯ menu to Settings
- make Graph | List and Filters small icon-only toggles

**Timeline (`transactions.html`):**
- The dates · accounts line and the ⋯ menu are gone.
- One row remains: a Graph | List icon pill on the left, reusing the header's `.icon-pill` and `.icon-pill-item` (40 px targets, `aria-current` tint). The links keep the accessible names "Graph" and "List".
- The Filters button is an icon on the right:
  - its screen-reader text is "Filters" or "Filters, on"
  - `.filter-button[aria-expanded="true"]` tints it while the panel is open
  - `.filter-dot` marks it while filters apply
- **Show money moving** (List only) moved to the top of the Filters panel. `flows.ts` still finds `[data-flow-toggle]` anywhere.
- **Follow-up (user, same day): under the chart and smaller.**
  - The row and its Filters panel are `components/timeline_tools.html`, included once:
    - after `chart_labels.html` in the Spending and Savings cards
    - otherwise under the range bar (List, or no data)
  - The two branches are complementary, so the ids stay unique.
  - `.icon-pill.is-small` makes the items 32 px with 16 px icons, and the dot is 6 px.
  - The panel is no longer a separate card; it opens right under the icons.
  - Checks: 229 Django tests OK; 14/14 Chrome checks; 360 px screenshots reviewed (graph light and dark, Filters open, List).

**Settings export:**
- "Your data" now has a GET form with a workspace (a select when there's more than one), From and To (this month by default), and Export CSV.
- It posts to `settings/export/` (`views.export`). That view checks the workspace is one the user can see (404 otherwise, including a non-number) and redirects to that workspace's `transaction_export` with the dates.
- The export keeps its date checks and two-year cap.
- The Timeline's filter-aware export (search, person, category, accounts) is gone with the menu. Settings exports every visible transaction in the range.

**Verification:**
- 229 Django tests OK. New: the Settings export picks a visible workspace and dates, and refuses others. Changed: the toolbar test.
- 14/14 Chrome checks:
  - `lanes.spec` turns the lines off from Filters
  - `settings.spec` downloads from Settings
  - `ranges.spec` and `transactions.spec` check the URL and the chart label instead of the removed dates line
- 360 px screenshots reviewed: graph (light and dark), Filters open, List, Settings export.

## One-line transaction rows — September 29

Why: the user asked to shrink the transaction listings: show only the amount, where it went and the date (as 0/0/00), open the details on tap and push the rest down, make Edit an icon, and add a way back from the edit page.

**Changes:**
- **`components/transaction_row.html`** (the Timeline, account and category pages):
  - Each row is a `<details name="transactions">`.
  - The summary shows the date (`n/j/y`), the name (truncated) and the amount (muted while pending), with a ▾ that turns over when open.
  - The details list Category (or the split lines), Type (with Pending), Account (where it was shown before), Original name and note, plus a pencil `.icon-button` that keeps the accessible name "Edit {name} on {date}".
  - The shared `name` makes opening one row close the other (Chrome 120+, Safari 17.2+; older browsers simply allow several open).
- **Timeline:** the day header rows are gone, and so is the `day_posted` lookup (and its grouped query in year views). Day totals remain in the Daily totals table.
- **`form.html`:** a `‹ Back` chip at the top whenever the page has a `cancel_url`, which includes the transaction edit page.
- **CSS:** `.txn-*` and `.icon-button`. The details fade in over 150 ms, with no motion under reduced motion.

**Verification:**
- 229 Django tests OK
- 14/14 Chrome checks: the five steps that click Edit open the row first
- 360 px screenshots reviewed: closed rows (about 45 px each, from about 76), an open row in light and dark, only one row open after opening another, and the edit page's Back chip; no sideways scroll

## Day lines, signs and Go to — September 29

Why: the user asked for a visible line between days in the transaction list, a day picker, and visible + or − on the totals. User choices: jump to the day; signs on every row and each day's total.

**Changes:**
- **Signs:** `labelled()` sets `row.money_in`.
  - Income and refunds come in and expenses go out; a transfer follows the bank's `money_in`.
  - `transaction_row.html` shows `+` or `−`.
  - The new `|signed` filter (`money.py`) formats a signed total with a true minus.
- **Day lines:**
  - `day_net()` is one grouped query over the days on the page, covering whole days even when paging cuts one.
  - It gives money in minus money out, posted only. Spending leaves transfers out; Savings uses the bank's direction (`_flows`).
  - The Timeline puts a `.day-line` (`id="day-YYYY-MM-DD"`, `data-day`) before each day's rows.
- **Go to:**
  - A GET form beside the heading: the current query as hidden inputs, `day`, and `action="#results-title"`.
  - The view reads `?day=` and starts the list at that day or the nearest earlier one (`paged`, so "Start from newest" shows). `day` is dropped from the tab and range links.
  - In `app.tsx`, a change scrolls to the day line when that day is on the page, and submits otherwise.
  - The Go button shows only without JavaScript (`.no-js-only`).

**Verification:**
- 230 Django tests OK. New: signs, day nets that leave out pending and transfers, the jump, and a bad `day`.
- The Timeline, savings and flows tests pass on Neon (22/22).
- 14/14 Chrome checks: `transactions.spec` checks the day line, the minus, and that Go to scrolls without leaving the page.
- 360 px screenshots reviewed: day lines with nets and a jump that loaded older days.

## Audit fixes — September 29

Why: the user pasted an outside AI audit of `e9d3a15`. I checked each finding against the code, and the user said "do it". Each fix below has a regression test that failed first.

**Money and data:**
- **Split totals follow the amount** (`rules.rebalance`, called from `categorize()`):
  - When a hand split no longer adds up to its transaction (a manual amount edit, or a pending charge posting with a tip), its lines are rescaled in proportion with `largest_remainder`, which now takes any whole-number weights.
  - Example: $30/$20 on $50 becomes $36/$24 on $60.
  - A line that rounds to nothing is removed, and a single line left is no longer a split. Rule splits already recomputed.
- **Category filter totals** (`reporting.category_share`): with a category filter, the Timeline chart, totals and day nets sum `share`: a split row's lines in that category, or the whole amount for any other row. The Budget tab already worked this way. Rows still show their full amount.
- **Bank-synced rows' type:**
  - `transaction_edit` redirects synced rows (`provider_id`) to the per-workspace editor, whose Type sync never overwrites.
  - Before, a type set on the row itself was lost at the next Plaid modification, and the whole-row save could write back a stale amount.
  - Trade-off: the type is now set per workspace.
  - Imported-file rows keep "Edit type", since nothing re-syncs them.
- **CSV export:**
  - It covers every visible account whatever the Spending | Savings switch says, with the filters and two-year cap as before.
  - Amounts are signed: negative is money out, by the row's direction (so transfers keep their direction).

**Bank connections:**
- **Disconnect:** Plaid is asked to remove the item first. On failure, the connection and its encrypted token stay, and the message says "Couldn't reach Plaid… try again". It still disconnects locally when Plaid says access is already gone (`ALREADY_GONE`: item not found, invalid token, or a replaced `PLAID_TOKEN_KEY`).
- **Daily catch-up:** it also retries connections whose last error is temporary (`RETRYABLE`, or any `HTTP_5…`). Ones that need the owner, such as signing in again, wait for them.
- **Timeout:** every Plaid call has a 5 s connect and 30 s read timeout. A timeout counts as `CONNECTION_FAILED`.

**Notifications:**
- `push_subscribe` checks the key shapes: a 65-byte P-256 point and a 16-byte secret, both base64url.
- `send_budget_alert` skips a device that fails in any other way.
- `deliver()` logs failures instead of raising, because it runs after the change has committed and must never turn a saved change into an error.

**Phone and browser:**
- **Prefetch:** it leaves out `/alerts/` (opening Alerts marks them read) and `/banks/` (bank pages make Plaid link tokens).
- **Swipe:**
  - A `touchcancel` springs back and never changes pages.
  - Back to a cached page clears the drag's inline offset on the page and the charts.
- **Pinch zoom:** `#main` uses `touch-action: pan-y pinch-zoom`, so pinch zoom works again.

**Deferred** (valid, but they need more than a fix):
- push ownership on a shared browser after logout
- durable, retried delivery (needs a worker)
- PostgreSQL in CI
- fresh browser fixtures per run

**Verification:**
- 236 Django tests OK (4 PostgreSQL-only tests skipped).
- 91/91 on Neon: timeline, splits, reporting, budgets, Plaid, push, savings, settings.
- `npm.cmd run build`; 14/14 Chrome checks on a restarted preview server.
- Not tested in a browser: the swipe cancel and pinch zoom. The Chrome checks have no touch cancel.

Continue: AI insights (6), statements (7) or the release gate (8), as the user prefers. Bklit charts land in milestone 2; Kokonut Insights action in milestone 6. Live Manus tracking awaits public domain/pages. Shared storage, performance targets, SMTP delivery and production security still require release verification.
