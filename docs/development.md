# Local development and verification

Updated 2026-09-25. Development-only foundation, not ready for real financial data.

## Where to work

Use `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation` on branch `feat/project-foundation`, tracking `origin/feat/project-foundation`. Work through `fcee2b6` was pushed to GitHub on 2026-09-25; later commits are local until a push is requested (see `AI_HANDOFF.md`). The original checkout is on `main` with synchronized docs. No merge, pull request, or deployment has occurred.

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

Run `npm.cmd run test:browser` in another terminal, then stop the server with Ctrl+C. The helper migrates a separate `.local/browser.sqlite3`, seeds the existing synthetic browser account, generates an ephemeral secret and forces console-only email. It redirects console email to `.local/browser-server.log` and request/error logs to `.local/browser-server-errors.log`; the invitation browser test reads only these local synthetic emails. Tests add synthetic accounts/groups per run. All databases, mail tokens, screenshots and results stay in ignored `.local/`. Never use these deliberately public synthetic credentials or this server with private records.

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

Continue: budget kinds (fixed/irregular/flexible) and splits (requested 2026-09-25), then phone push. Still open from milestone 2: CSV import. Bklit charts land in milestone 2; Kokonut Insights action in milestone 6. Live Manus tracking awaits public domain/pages. Shared storage, performance targets, SMTP delivery and production security still require release verification.
