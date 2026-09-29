# Low-fidelity wireframes and user flows

Status: full-release wireframes remain a UX draft; a low-fidelity foundation subset now exists. Updated 2026-09-25. All names/amounts below are illustrative.

## Current foundation subset

Implemented journey: sign in -> Personal accounts -> add a manual account -> create/select a group -> Manage sharing -> choose owned accounts and confirm past/future history -> Save sharing. Members can leave; owners can remove members. Account detail is an empty-state page, not a transaction report.

Temporary navigation exposes only working destinations: Accounts, Add account, New group. Workspace links show the active context. It will become the five-destination navigation below as those screens land; no dead dashboard/chart buttons are presented as working.

Neutral grayscale, system typography, Flowbite-style forms/cards/navigation, local Tailwind CSS and a brief Motion confirmation highlight implement the low-fidelity direction. No global Flowbite DOM initializer or React mounts exist yet. Invitations and recovery were added on 2026-09-24. Separate added/removed sharing review, unsaved-form protection and remaining full-release journeys are pending. Browser checks and screenshot review status are tracked in [development verification](development.md).

Invitation journey: group owner -> Invite someone -> intended email plus existing-history confirmation -> send/revoke pending invitation. Recipient -> invitation -> Sign in, or Create invited account -> request separate setup email -> open one-hour setup link -> choose username/password -> sign in -> explicitly Join group. Existing accounts use Email verification -> request email -> open link while signed in -> confirm -> return to invitation. Joining shows a notice to existing account owners with a Review your sharing link. It never shares the joining person's accounts. The login page offers password recovery for verified email addresses; expired recovery links offer another request.

Read alongside the [product spec](superpowers/specs/2026-09-22-budget-app-design.md) and [build plan](superpowers/plans/2026-09-22-budget-app.md). Permissions and financial calculations remain defined by the spec.

Implemented 2026-09-25: workspace summary with ← / → and Month/Year (year adds a per-month table linking to each month) -> View <period> transactions -> search/filters (Apply filters, Clear filters, Older transactions) -> Edit -> Save returns to the same filtered list. Filters are a plain form above the list, not yet a dialog.

Update 2026-09-25 (requested features): Reports, Goals, Bills & recurring, and Net worth need low-fidelity wireframes and flows before they are built (spec: Requested additions). Proposed placement:
- Reports and Net worth open from Overview.
- Goals and Bills & recurring sit under Budgets.
- Alert preferences (thresholds, bill reminders, unusual activity, email or push) go under Settings.

Update 2026-09-25 (speed pass): charts hold their exact space while loading (a placeholder line appears only if loading takes over 1.5 s, and the chart is excluded from the page crossfade); tab pages are prefetched and pages crossfade (the bottom nav stays put); Add to Home Screen opens the app full screen.

Update 2026-09-28 (Plaid slice 2): A connection that needs a new bank sign-in shows "Needs you to sign in again" and a Reconnect chip, on Settings → Bank connections and on the account page. Reconnect opens the same Connect page, titled "Reconnect <bank>". Choose accounts shows a notice when that bank is already connected; lookalike accounts are unticked with "Looks like one you already import from another connection".

Update 2026-09-28 (Plaid sandbox): Settings → Add → Connect a bank → Continue with Plaid (Plaid's window; sandbox hint) → Choose accounts (all ticked, each private; already-imported ones are shown greyed) → Overview with a sync message. Settings → Bank connections: institution · N accounts · Updated X ago, with Sync now / Accounts / Disconnect. A synced account's page shows "Bank, synced through Plaid", its sync status and Sync now.

Update 2026-09-28 (email alerts): Settings → Notifications holds Email alerts (On/Off with one Turn on/Turn off button, and a verify-first hint) above This device (push). Each email's unsubscribe link opens a no-sign-in "Turn off email alerts?" page with one button, then "Email alerts are off".

Update 2026-09-28 (CSV import): The account page has Import CSV next to Add transaction and an Imports list with Undo import. Upload leads to one Check file.csv page: Columns (header row, date, description, amount or money out, optional money in, sign, money-in type, optional category) → Update preview → preview rows (money in with +) → a collapsed "N look already imported" list with tick-to-keep → Import N transactions / Cancel. Row errors appear at the top and nothing is saved. This sits on the account page rather than More → Imports for now.

Update 2026-09-25 (split rules and push): Add rule has an optional Split with + share (%). Settings has a Notifications card (Turn on/off for this device, with an iPhone Home Screen hint), shown only when push is available.

Update 2026-09-25 (budget types and splits): Add budget has a Type (Fixed bill / Yearly or irregular cost / Flexible spending) and a due day for fixed bills. Budgets shows a Monthly plan (estimate) card: income, fixed bills, set-asides, disposable income, flexible budgets, and what is unplanned. The transaction Edit page links to Split across categories, with up to four category and amount lines that must add up exactly.

Update 2026-09-25 (categorize by example): Category → Add transactions has a search box, a ticked result list (hand-set rows unticked and labeled), a "Future transactions containing this go to <category>" option with an editable keyword, and "Add ticked to <category>". The transaction Edit page has "Also put other transactions with this name in this category" with a prefilled Name contains field. A filtered Timeline has an "Add transactions to <category>" chip.

Update 2026-09-25 (budgets and alerts): Overview has a Budgets card above By category (spent of limit, bar, left/over) with Manage budgets (replaced 2026-09-28 by the top card's Chart | Budgets switch, section 2). The header has a bell that becomes an "N new alerts" pill; it opens Alerts, a list of over-budget events with current amounts.

Update 2026-09-25 (categories): Overview has a By category list (bar per category, tap to open the filtered Timeline) and a Manage categories link. Categories → Rules → Add rule has Preview matches and an Also apply to existing transactions option. The transaction Edit page has a Category field.

Update 2026-09-25 (latest): More is now **Settings** (Your login: change username/email/password; Appearance: System/Light/Dark; Your data: CSV export; Add; Sign out), and the Timeline has an Export CSV chip.

Implemented later on 2026-09-25: bottom navigation is Overview | Timeline | More (More became Settings; Budgets opens from Overview; Insights joins when built). More holds Your login (Change password, Email verification, Sign out) and Add (Add account, New group, Invite someone to Budget). The workspace switcher is a one-line disclosure (Workspace: name). Timeline = filters -> range totals -> Daily totals table (disclosure) -> day-grouped feed -> Older transactions / Start from newest; a changed list restarts with a status note. Standalone invite: More -> Invite someone to Budget -> email + confirmation -> recipient opens link -> Create your login -> setup email -> choose username/password -> sign in -> Finish -> own Personal workspace only.

Implemented 2026-09-25 (night): Robinhood-style visual layout in the user's palette. Overview = workspace name -> big period spending number -> change vs previous month/year -> bare running-total chart -> ← Month Year → chips -> Posted/Pending/Income rows -> View timeline row -> accounts with a per-account spending pill. Timeline = ‹ back link -> title/range -> big number -> chart -> stat rows -> Daily totals table -> Filters (disclosure, open when active) -> day-grouped feed. Bottom nav has icons with labels. Light: white with Bubblegum Pink/Lavender Blush; dark (OS setting): Coffee Bean with Black Cherry.

## Navigation and reusable components

Header (user sketch, 2026-09-28):
- Row 1: `Budget.`, then at the right Invite (Manage sharing in a group), the bell, and the username (hidden on phones).
- Row 2: the workspace selector (a dropdown), with the **Spending | Savings** switch beside it on the Overview and the Timeline.
- Pages don't repeat the workspace name.

```text
Budget.                          [+ Invite]  (bell)  browser-check
[Workspace: Personal v]  [Spending | Savings]
```

Update (user, 2026-09-28):
- **One pill:** + (Invite) and the bell share one border; the + is just a sign. In a group, a people icon opens Manage sharing.
- **Phones:** the switch is right-aligned, and the selector is the same height as the switch (40 px).

```text
Phone
Budget.                         ( +  bell )
[Personal v]              [Spending | Savings]
```

The active workspace stays visible: Personal, Partner group, or a named Friends group. Switching context changes transactions, budgets, rules, and insights together. Ask before discarding an unsaved edit; never transfer a draft or permission decision silently between workspaces.

Phone destinations: Overview, Timeline, Budgets, Insights, More. More opens a page containing Accounts, Sharing & people, Statements & imports, Notifications, and Settings. A notification button is also available in the header. Desktop uses the same destinations in a sidebar.

| UI need | Selected component source | App-specific work |
| --- | --- | --- |
| Phone/desktop shell | Flowbite bottom navigation, sidebar, dropdown | Routes and current workspace. |
| Overview | Flowbite cards, badges, progress bars, buttons | Authorized totals, budget status, freshness. |
| Spending history | Flowbite timeline, list group, table, pagination | Dates, cursor paging, amounts, transaction links. |
| Filters/editors | Flowbite forms, select, checkbox, drawer/modal | Validation, permissions, save/back behavior. |
| Sharing | Flowbite list group, checkbox/toggle, alert, modal | Who sees which account and confirmation. |
| Alerts/results | Flowbite alerts, toast, badge, skeleton, spinner | Job state, retry action, inbox persistence. |
| Charts | Bklit UI React charts | Daily/cumulative/category series, touch/keyboard selection, equivalent HTML table. |
| Insights request/status action | Selected Kokonut UI interactive component | Existing generate/status workflow, clear labels, focus, and failure recovery. |
| Component transitions | Motion | Brief feedback; honor reduced motion and display confirmed values immediately. |

References: [Flowbite catalog](https://github.com/themesberg/flowbite), [Django integration](https://flowbite.com/docs/getting-started/django/), [Bklit UI](https://github.com/bklit/bklit-ui), [Kokonut UI](https://kokonutui.com/docs), and [Motion accessibility](https://motion.dev/docs/react-accessibility). Use selected open-source components and a shared Tailwind theme; paid templates are not assumed. React owns only its mounted component containers; Flowbite controls the surrounding server-rendered UI. Exact Kokonut component selection follows flow review and compatibility checks.

Animation does not change these journeys: keep workspace context, Back/Cancel, status text, and monetary values visible without waiting for transitions. Reduced-motion mode retains every action. Charts keep an accessible server-rendered table and selected-date summary even if their JavaScript fails to load.

Manus SEO is an operator workflow for public pages, not a destination in the finance app. No authenticated workspace, chart payload, purchase, or insight is sent to SEO tracking. Django remains the backend. Public-page scope and the tracked domain are still to be selected; no public landing-page design or live tracking is claimed here.

## 1. First use: connect privately, then choose sharing

Journey: sign in/accept invitation -> choose workspace -> connect bank or import CSV -> select accounts -> initial import -> Overview. Linking is always owned by the signed-in person. Sharing is a separate explicit action.

```text
+----------------------------------+
| Personal v               Alerts  |
| Add your first account            |
|                                  |
| Track spending in one place.     |
| New accounts start private.      |
|                                  |
| [ Connect a bank ]               |
| [ Import a CSV instead ]         |
|                                  |
| Your accounts                    |
| No accounts connected yet.       |
|                                  |
| Overview Timeline Budgets        |
|           Insights More          |
+----------------------------------+
```

The two-line navigation here is notation for the five destinations, not a prescribed two-row bottom bar. Actual layout must fit readable labels/hit areas at the minimum viewport.

Bank connection opens Plaid's existing Link UI. Reuse that flow; do not design a bank-password form. On return, list available accounts with import checkboxes and a Private badge. Cancel returns safely to Accounts. A partial initial import shows Loading history and the last bank update; it does not show a misleading zero-spend final result.

## 2. Overview: understand the period, then inspect

Update (user, 2026-09-29, with a sketch):
- **Range bar:** the `← 1M 1Y Lifetime →` bar is the first row under the header, in the same place on the Overview, the Timeline and the Savings page.
- **Smaller total:** the total is smaller, so up to $999,999,999.00 fits on one line.
- **Chart | Budgets:** one icon on the total's line, at the right. It shows the view it switches to.
- **Chart height:** the chart is shorter, capped at 13rem.

```text
Phone
[← 1M 1Y Lifetime →]
$5,878.56 (i)                 (≡)   ← (≡) shows Budgets; in Budgets it's a chart icon
[chart, shorter]
```

Update (user, 2026-09-28):
- **Period chips:** `← 1M 1Y Lifetime →`. 1M and 1Y are the calendar month and year, and the arrows step through them.
- **Lifetime** runs from the first transaction to today:
  - no arrows and no comparison
  - "Lifetime spending · since March 2026"
  - a chart by month and a per-year table
  - the Budgets panel asks for 1M or 1Y
- **The note under the total:** inline on wider screens. On phones an (i) opens it as a small popup that closes on a tap elsewhere, Escape, or focus leaving the (i).

```text
Phone
$5,878.56 (i)          → (i): | September 2026 spending · ↗ $1,064.63 more than August |
[chart]
[←  1M  1Y  Lifetime  →]
```

Journey: select workspace/period -> see posted spend and budget status -> tap category/budget/recent transaction -> matching timeline or purchase.

```text
+----------------------------------+
| Partner group v          Alerts  |
| < September 2026 >     Month/Year |
|                                  |
| Posted spending          $1,240  |
| Pending                    $38  |
| Updated 10 minutes ago           |
| [ Sync my accounts ]             |
|                                  |
| Budgets                 View all |
| Dining     $212 / $200   $12 over |
| [====================]           |
| Groceries  $180 / $400            |
| [=========           ]           |
|                                  |
| Recent spending         View all |
| Sep 22  Grocery store       $45 > |
| Sep 21  Cafe                 $8 > |
|                                  |
| Overview Timeline Budgets        |
|           Insights More          |
+----------------------------------+
```

Sync my accounts only refreshes connections owned by the current user, even in a group. Show each connection's state and allow retry/reconnect from Accounts. Other members' shared data shows its own freshness; membership does not grant control of their connections. Empty budgets offer Create a budget. Always label money as posted/pending rather than blending the two.

**Compact Overview (user, 2026-09-28):**
- A small **Chart | Budgets** switch on the top card replaces the separate Budgets card.
- The Year view counts monthly budgets × 12.
- The choice is remembered on this device. Without JavaScript the budget list shows.

```text
Personal                                   [+ Invite]
$1,234.56
September 2026 spending · ↗ $20 more than August
                                     [Chart | Budgets]
Budgets view:
  Groceries      ████░░  $320 of $400      $80 left
  Dining         ██████  $210 of $200      $10 over
  Rent · fixed   Paid    $1,500 of $1,500
  Car insurance · 2026   $600 of $1,200   $600 left   (yearly; not in the month total)
  This month: $2,030 of $2,100 · $80 left · $10 over
  Manage budgets ›
[←  Month  Year  →]
```

## 3. Timeline: investigate, filter, and edit

Journey: Timeline -> filters/date/chart point -> purchase -> edit -> save -> return to the same position and filters.

```text
+----------------------------------+
| Partner group v          Alerts  |
| Timeline          September  v   |
| [ Search merchant ] [ Filters ]  |
|                                  |
| [ Daily / Cumulative chart ]     |
| Selected: Sep 22     Spent $45    |
| [ View chart data as a table ]   |
|                                  |
| Sep 22                    $45    |
| o Grocery store            $45 > |
|   Groceries / Your checking      |
| Sep 21                     $8    |
| o Cafe                      $8 > |
|   Dining / Friend's account      |
|                                  |
| [ Load more ]                    |
| Overview Timeline Budgets        |
|           Insights More          |
+----------------------------------+

+----------------------------------+
| < Back       Edit purchase       |
| Partner group                    |
| Grocery store        Sep 22 $45  |
| Original bank amount: read-only  |
|                                  |
| Display name [ Grocery store ]   |
| Category     [ Groceries     v ] |
| Type         [ Expense       v ] |
| Group note   [                 ] |
|                                  |
| [ Create a rule for this name ]  |
|                                  |
| [ Save changes ]     Cancel      |
+----------------------------------+
```

For another member's purchase, show a read-only detail page, not a Save button. Notes explicitly say Personal note or Group note. Filters include category, merchant, account, person, and dates; apply/reset is visible. No matches offers Clear filters. Failed save preserves input; discard confirmation protects unsaved edits. Keyboard-open behavior must keep fields and actions accessible.

Rule journey: create from purchase -> choose exact merchant/description contains -> select or create category -> preview affected existing purchases -> choose Apply to existing history -> save rule. Preview states that manual category overrides will be preserved. Future matches use the saved rule automatically. A background backfill shows progress and a link back to results.

## 3b. Timeline by account (2026-09-28)

Update (user, 2026-09-29): the range chips are now the shared range bar, first row, `[← 1M 1Y Lifetime →] … (⋯)`. The arrows step a calendar month or year and keep the filters; a custom range has no arrows. The "Timeline" heading is screen-reader only (the tab names the page). Below: dates, then `[Graph|List] … [Filters]`.

Update (user, 2026-09-28): the Timeline has range chips, **1M | 1Y | Lifetime**:
- 1M and 1Y are the calendar month and year of the current range's end; Lifetime starts at the first transaction.
- The chips keep the other filters, and they don't count as "Filters · on".
- On phones they get their own row above Graph | List and Filters.
- Lifetime past two years charts and totals by month.

Decisions (user, 2026-09-28):
- the account view lives on the Timeline page
- none ticked means all accounts, the total
- a second layout, **List** (first called Side by side), shows one dated list per account
- lines connect money moving between your own accounts only: transfers and card payments. Spending and income stay plain rows.

```text
Timeline                               [Graph | List]
Accounts · 3 of 14 ▾   [x] Checking ••0000 [x] Savings ••1111 [x] Card ••3333 [ ] …  [Show]
[x] Show money moving                      (List only)
┌ scrolls both ways (max 75vh) ─────────────────────────────────────────┐
│ Checking ••0000     │ Savings ••1111     │ Card ••3333                  │ sticky
│ in +3,000 out −910  │ in +500            │ in +410 out −6               │
├─ Sat, Sep 28 ───────┴────────────────────┴──────────────── (sticky left)
│ Payroll     +3,000  │                    │                              │
│ To savings    −500 ─┼──▶ From chk   +500 │                              │
├─ Thu, Sep 26 ─────────────────────────────────────────────────────────
│ Card payment  −410 ─┼────────────────────┼─▶ Payment              +410  │
│                     │                    │   Starbucks              −6  │
├─ Wed, Sep 25 ─────────────────────────────────────────────────────────
│ Venmo  −200 ─▷ elsewhere                                                │
└───────────────────────────────────────────────────────────────────────┘
```

**Flows:**
- Timeline → tick accounts → Show. The totals, chart, list and CSV export all follow the ticks.
- List → scroll sideways through the lanes. Hover or focus a transfer to light up the other side.
- Show money moving: turn the lines off or on. The choice is remembered on this device.

**Text carries the meaning:** every paired row also says where the money went ("To Savings ••1111", "From Checking ••0000, Oct 2", "To elsewhere"). A line to elsewhere is a short stub ending in a small circle, so it never looks aimed at the next lane. Screen readers and a failed script lose nothing.

**Phone:** each lane is about 85% of the screen wide, so the next one peeks in. Lanes snap as you scroll, and the page itself never scrolls sideways.

**Empty and limits:**
- With nothing ticked, only accounts with transactions in the range get a lane.
- An empty ticked lane says "No transactions in this range."
- Over 400 rows: "Showing the newest 400 transactions. Narrow the dates to see older ones."

**Compact controls (user, 2026-09-28):**
- The layout buttons are now **Graph | List** (they were Together | Side by side); the List view's heading is "By account".
- Export CSV and Show money moving live in a ⋯ menu at the top right.
- The account tick boxes, with Select all, appear only inside Filters.
- The filter fields sit side by side: 2 columns on a phone, 4 on a desktop.

```text
Timeline                                   [⋯]  → Export CSV · [x] Show money moving (List)
Sep 1 – Sep 28, 2026 · 2 of 14 accounts
[Graph | List]                 [Filters · on ▾]
┌ Filters ───────────────────────────────────────────────────┐
│ Search [.....................]   Person [▾]   Category [▾]  │
│ From [date]   To [date]                                     │
│ Accounts · 2 of 14                          [Select all]    │
│ (x) Checking ••0000  ( ) Savings ••1111  …  (scrolls)       │
│ [Apply filters] [Clear filters]                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Budget and alert: set a threshold and act on it

Journey: Budgets -> Create budget -> select category or merchant -> enter positive limit and monthly/yearly period -> save -> inspect progress. Push activation is optional and does not block saving a budget.

```text
+----------------------------------+
| < Budgets       Partner group    |
| Dining                           |
| September 2026                   |
| $212 spent / $200 budget         |
| $12 over                         |
| [====================]           |
|                                  |
| [ View matching transactions ]  |
| [ Edit budget ]                  |
|                                  |
| Notifications                    |
| In-app: enabled                  |
| This phone: not enabled          |
| [ Enable push on this phone ]    |
+----------------------------------+
```

Alert journey: threshold crossed -> inbox/push -> sign in if needed -> affected budget -> filtered transactions. Show pending separately and explain that alerts follow bank updates. If access was revoked, show This item is no longer available and link to current Overview; never display saved private detail.

## 5. Share finances with a friend

Journey: More -> Sharing & people -> create/select group -> invite person -> friend accepts -> each owner chooses accounts to share -> shared Overview. Account owners can share after creating the group or after acceptance; preview who can see the data in either case.

```text
+----------------------------------+
| < Sharing        Friends group   |
| Members: You, Alex               |
| [ Invite someone ]               |
|                                  |
| Your accounts in this group      |
| [x] Chase checking               |
| [ ] Chase credit                 |
| [ ] Marcus savings               |
|                                  |
| Alex will see past and future    |
| transactions for selected        |
| accounts. Personal notes and     |
| statement PDFs stay private.     |
|                                  |
| [ Review sharing changes ]       |
+----------------------------------+
```

Review shows the added/removed accounts and current recipients before Save sharing. Newly invited members will see accounts already shared with the group: disclose this before sending the invitation and notify account owners when membership changes. A friend can share their accounts back, but accepting an invite never automatically shares their personal data. Revocation updates the group's totals/timeline and cancels access-dependent outputs. Offer a separate two-person group when the owner wants to share with one friend rather than every member of an existing group.

AI permission is not hidden inside this sharing form. A separate account/provider consent step is required before external AI processing.

## 6. AI insights: understand scope and cost before sending

Journey: Insights -> configure personal key if missing -> choose workspace/period -> review eligible accounts and payload -> request analysis -> progress -> findings with links to source totals/timeline.

```text
+----------------------------------+
| Partner group v          Alerts  |
| Insights          September v    |
|                                  |
| Analyze spending patterns        |
| Key: configured (yours)          |
| 2 of 3 shared accounts eligible  |
| 1 owner has not enabled AI use   |
|                                  |
| [ Review data being sent ]       |
| Estimate: shown before request  |
| Remaining daily allowance: ...   |
| [ Generate insights ]            |
|                                  |
| Results are visible only to you. |
+----------------------------------+
```

The ellipsis is a wireframe position for the user's actual configured allowance, not permission to ship placeholder copy. Preview uses plain language for categories/totals shared with the selected provider. Key input appears only in Settings and is masked after save. Missing consent gives a partial-analysis notice, not an attempt to grant permission for another owner. During generation show progress and allow navigation away; return to the same job without another charge. Failure retains context and explains whether retry could incur another charge.

## 6b. Planning tools: net worth, bills, goals (2026-09-28)

Decisions (user, 2026-09-28):
- no Reports
- Goals are off until turned on in Settings, per person
- bill reminders come 3 days before a due date
- net worth counts synced bank balances plus manual items

Net worth opens from Overview. Bills & recurring and Goals open from Budgets.

```text
Overview (card appears once any account has a balance)
| Net worth            $182,400 › |
| Own $214,900 · Owe $32,500      |

Net worth                      (estimate from last known balances)
| $182,400                                  |
| Own                                        |
|  Plaid Checking ••0000   $1,250  2h ago  › |
|  Home (manual)         $400,000  Sep 28  › |
| Owe                                        |
|  Plaid Credit Card ••3333  $410  2h ago  › |
|  Car loan (manual)      $12,300  Sep 28  › |
| Not counted: Old wallet            Set ›   |
| [Add something you own or owe]             |

Budgets page (new cards)
| Bills & recurring                       › |
| Next: Rent $1,500 due Oct 1 (in 3 days)   |
| Goals (only if turned on)               › |
| Emergency fund ██████░░ 62% · $250/mo      |

Bills & recurring
| Next 30 days (estimate)                    |
|  Oct 1  Rent            $1,500             |
|  Oct 3  Payroll        +$3,000             |
|  Bills $1,500 · Income $3,000 · Left $1,500 |
| Your recurring bills and income            |
|  Rent · monthly · $1,500 · reminder on   › |
| Found in your transactions                 |
|  Spotify · monthly · ~$11.99 (4 times)     |
|  [Confirm] [Not recurring]                 |
| [Add a bill or income]                     |

Goals (Settings → Goals: On)
| Emergency fund · savings                   |
|  ██████░░ $6,200 of $10,000 · by Jun 2027  |
|  About $423/month to get there           › |
| [Add a goal]                               |

Alerts inbox: bill reminders sit with budget alerts
|  • Bill due Oct 1: Rent · $1,500           |
```

Flows:
- **Manual item:** Net worth → Add something you own or owe → name, own or owe, value → back to Net worth.
- **Recurring bill:**
  - Budgets → Bills & recurring → Confirm a found series (or Add), then edit its amount, due date, interval and reminder.
  - 3 days before each due date, everyone in the workspace gets an Alerts entry. Push and email carry only "A bill is due soon".
- **Goal:** Settings → Goals → Turn on → Budgets → Goals → Add a goal (savings or debt, target, optional date, an optional linked account) → progress and the monthly amount needed.

Empty states:
- no balances: the Net worth card is hidden and the page explains how to add a value
- no bills: "Bills that repeat show up here after three payments; or add one"
- Goals off: no goal UI anywhere

## 6c. Savings (2026-09-28)

Decisions (user, 2026-09-28):
- savings accounts are marked automatically from the bank type (savings, money market, CD), plus a **Savings account** switch on every account
- a Savings page reached from an Overview card

Update (user, 2026-09-28: "instead of scrolling down to savings, make it toggleable"): the Overview top card has a **Spending | Savings** switch in place of the separate Savings card. Savings mode shows:
- the total and net saved against the previous period
- the saved-so-far chart
- the shared Month/Year nav
- Money in, Money out and Net saved
- View savings transactions ›, and Savings accounts and details › (this page)

The choice is remembered on the device.

Update (user sketch, 2026-09-28):
- The switch moved to the header, beside the workspace selector. It works on both the Overview and the Timeline, as one mode for both.
- The workspace name above it and the Timeline's "‹ Personal" link are gone, and Invite sits by the bell.

User choices:
- **Timeline in Savings:**
  - only the savings accounts' transactions
  - the top card: net saved, the saved-so-far chart, Money in / Money out / Net saved, and a daily In / Out / Saved so far table
  - each day's header shows that day's net
  - search, dates and Graph | List still work
- **Overview in Savings:** the By category card, which only covers spending, is hidden.

```text
Overview top card (Savings)
[Workspace: Personal v]  [Spending | Savings]
$12,400
September 2026: +$300 saved · ↗ $120 more than August

Savings                      ‹ Personal
$12,400            ← total of last known balances
September: +$300 saved · ↗ $120 more than August
   ‾‾\__/‾‾‾‾\_/‾   saved so far this month (dips on withdrawals)
[←  Month  Year  →]
Money in        $1,000
Money out         $700
Net saved        +$300
View savings transactions ›   → Timeline List view with these accounts ticked
(Year view: a month-by-month In / Out / Net table)

Savings accounts
  Demo Savings ••9910      $12,400   +$200
  Rainy day                $2,000    +$100
  Emergency jar            No balance · Add one
```

- **Transfers:** a transfer to checking is money out here. It counts as spending only once the money is spent from checking, so it's never counted twice.
- **Empty state:** "No savings accounts yet. To add one, open an account, choose Edit and turn on Savings account."

## 7. Secondary paths and recovery

| Starting point | Happy path | Required recovery |
| --- | --- | --- |
| More -> Statements | Owned account -> month -> download bank PDF or upload a PDF | Unsupported bank offers upload; reject invalid files without losing account selection. |
| More -> Imports | Owned account -> choose CSV -> map columns -> preview -> import job -> results | Invalid rows show row errors before commit; overlap review keeps legitimate duplicates. |
| Accounts -> connection warning | Reconnect through Plaid -> sync resumes | Cancel keeps existing history and reconnect notice. |
| Notification settings | Enable device push -> browser permission -> confirmation | Denial explains browser settings; inbox remains usable. |
| Offline / interrupted network | Clear connection status -> retry when online | Preserve unsaved input within the current page; do not queue financial edits silently. |

## Desktop adaptation and review tasks

```text
+------------+----------------------------------------------+
| Workspace  | Period / filters                    Alerts   |
| Overview   |                                              |
| Timeline   | Main list / chart       Selected detail      |
| Budgets    |                                              |
| Insights   |                                              |
| More       |                                              |
+------------+----------------------------------------------+
```

Use the same selected components, routes, labels, and permissions across breakpoints. Additional width permits a second column; it does not introduce a separate workflow. The main page scrolls naturally; keyboard focus and screen-reader reading order follow the meaningful content order.

Review by walking through these tasks, then amend the wireframes before polishing screens:

1. Connect a bank without sharing anything, then share only checking with a friend.
2. Find yesterday's purchase, change its category, and create a rule for matching history/future imports.
3. Find why a budget is over its limit from an inbox alert.
4. Identify which workspace and which people an edit or sharing action affects.
5. Generate an insight, explaining which accounts are omitted and whose key pays.
6. Recover from cancelled bank linking, failed save, denied push, revoked sharing, and offline mode.
7. Repeat chart selection and the Insights action with reduced motion enabled and with enhancement loading unavailable; keep financial values and recovery paths usable.

Success means users can identify their next action, current scope, consequence, and recovery path. The full-release flows remain reviewable artifacts; the foundation subset is implemented. Automated browser checks do not replace user usability testing, which has not been performed.
