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

## Next

Continue milestone 2: timeline, CSV import/export and Bklit charts. Bklit charts land in milestone 2; Kokonut Insights action in milestone 6. Live Manus tracking awaits public domain/pages. Shared storage, performance targets, SMTP delivery and production security still require release verification.
