# Local development and verification

Updated 2026-09-23. Development-only foundation, not ready for real financial data.

## Where to work

Use `C:\Users\bmauricio\Documents\budget\.worktrees\project-foundation` on branch `feat/project-foundation`. The original checkout is on `main`; existing documentation edits were preserved and copied into the worktree. The foundation is committed locally. A push to `origin` was rejected by automated security review because remote ownership and destination authorization could not be verified; nothing was pushed, merged, or deployed.

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

Open `http://127.0.0.1:8000/`. No admin route or public registration exists; the operator-created user signs in through the app. Invitations/recovery are unfinished. Do not expose runserver publicly. Supply a stable secret through the environment to persist sessions across restarts; never commit it. .env.example is a reference, not auto-loaded.

For PostgreSQL, unset BUDGET_LOCAL_SQLITE, configure PG variables from .env.example and use a dedicated development database/user. No existing database credentials were read or guessed. SQLite is rejected with DEBUG off; passing SQLite checks do not prove row-locking or multi-instance correctness.

## Checks

```powershell
.venv/Scripts/python.exe manage.py test --settings=config.test_settings --noinput
.venv/Scripts/python.exe manage.py check --settings=config.test_settings
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.test_settings
npm.cmd run build
```

config.test_settings is synthetic-test-only: public test secret and fast password hashing. Never use it for personal data/deployment.

Browser checks require locally installed Google Chrome, the development server above and a disposable local database. Seed the synthetic browser user once:

```powershell
.venv/Scripts/python.exe manage.py shell -c "from budget.models import User; User.objects.create_user('browser-check', password='synthetic-browser-check-only')"
npm.cmd run test:browser
```

These deliberately public synthetic credentials are not production credentials. Browser tests add synthetic accounts/groups per run. Screenshots/results go to ignored .local/. Never use this test user with private records.

## Verified /compact checkpoint

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

## Next

Resume milestone 1 with invitations/email verification/recovery, then PostgreSQL concurrency checks before milestone 2 transactions/CSV/reporting. Complete the deferred account-creation revision update before derived outputs use it. Bklit charts land in milestone 2; Kokonut Insights action in milestone 6. Live Manus tracking awaits public domain/pages. Shared storage, performance targets and production security still require release verification.
