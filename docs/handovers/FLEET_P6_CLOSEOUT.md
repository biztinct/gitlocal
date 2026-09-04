# FLEET P6 — support access with a trail. CLOSEOUT.

Built and validated 2026-09-03. Live on `payobook` (master), `payobook_template`
and `abm` at release **2026.09.03-6**. Spec: `FLEET_P6_SUPPORT_ACCESS.md`.
Ledger entries this phase added: **F62 – F68** in `FLEET_PROGRAM.md`.

## What is true now that was not this morning

1. From a customer's page in the cockpit, **Open as support** asks why, offers
   three lengths (30 min / 2 h / 8 h) and — when a practice copy exists — asks
   which copy first. It writes a one-time row on that customer's database and
   opens the link itself in a new tab. The link is good for **60 seconds** and
   for **one use**.
2. **Every session is written on the customer's own database**, where anyone who
   manages permissions for their company reads it under
   **Settings → About Payobook → Support access**: who, when, why, how long they
   were allowed, how long it actually lasted, from where, how it ended, and every
   screen that was opened. Nothing on any screen — ours included — deletes a row.
3. **The customer holds a switch.** Off means the cockpit's button is gone, with
   their own answer written where it was. There is no override in the code and
   none on the screen, and the customer's page says so in as many words.
4. **The support user cannot forget where they are.** A rose bar on every page
   names the company, counts down, pulses once at five minutes, and has *Leave*
   instead of a close button. The session ends by itself when the time is up.
5. **No password exists for the recovery account, still.** Entry is the hashed
   one-time token and nothing else.

## The shape of it

| Piece | Where |
|---|---|
| `pb.support.access` (the record) + `token_check` (pure) | `pb_tenancy/models/support.py` |
| The login seam (`_check_credentials`, `pb_support_token`) | `pb_tenancy/models/res_users.py` |
| The door, the calm pages, `leave`, `seen`, the rate limit | `pb_tenancy/controllers/support.py` |
| The clock, the screen log, `session_info` | `pb_tenancy/models/ir_http.py` |
| The rose bar | `pb_tenancy/static/src/js/support_bar.js` |
| The customer's page (the hero) | `pb_tenancy/static/src/js/support_page.js` |
| `support_open` / `support_history` / `support_end` | `pb_tenants/models/support_service.py` |
| The refusals, as pure functions | `pb_tenants/models/support_rules.py` |
| The cockpit row, dialog and history | `pb_tenants/static/src/js/tenants.js` + `xml/tenants.xml` |

Manifests: `pb_tenants` 19.0.2.1.0, `pb_tenancy` 19.0.1.4.0. One shared glyph
(`logOut`) was added to `pb_import_kit`'s registry.

## Decisions taken here, and why

- **The customer-side page is gated on the "who here can do what" permission**
  (`biz_access.group_access_manager`), not on `base.group_system`. On a
  customer's database `group_system` is the PLATFORM's group — the tenant-admin
  rails exist to take it away from the customer's own administrator — so gating
  the record of OUR access on it would put it behind a door only WE hold. The
  hub gates categories rather than cards, so the card is registered once the
  permission answer comes back (2.5 s after first paint) and the SERVER refuses
  the data either way. A reader who reaches the page without the permission gets
  a sentence saying who in their company can help, not an error dialog.
- **A practice session raises no alert and is not written on the customer's own
  screen** — it is a throwaway copy, and an alert about one teaches the owner to
  scroll past the alerts that matter.
- **`pending_deletion` customers can still be helped.** They still have a
  database, and their last month is a real thing to need help with.
- **The reason must be at least six characters.** A shrug in a box is not a
  reason the customer can read in a month's time.
- **The switch ends what is running.** "Not now" has to mean now, or the switch
  is a decoration.

## What was verified live

| Check | Result |
|---|---|
| Release 2026.09.03-6 cut and rolled out | rehearsal (abm-staging) 2 min → template 9 s → abm 1 min |
| Tests, `-u pb_tenants,pb_tenancy` on the master | **454 tests, 0 failed, 0 errors** |
| Entry URL on abm | `https://abm.payobook.com/pb_tenancy/support/<token>` → **303 → `/bizapp`** |
| Bar on the customer | "You are in AB Mauri as Payobook support · ends 06:09 · 29m left · Leave" |
| Bar in the last five minutes | deepens and pulses once (`closing pulsed`) |
| Leave | session ended, signed out, lands on the finished page |
| Reuse of the same link | "This support link cannot be used" |
| Session past its finish time | next click → signed out → finished page |
| Customer switch OFF | cockpit button gone; their sentence in its place; live session ended |
| Suspended + support (practice copy) | ordinary user meets the paused page; support gets in |
| Email to the owner | sent at the press of the button — "For information: Payobook support opened AB Mauri" |
| Morning summary | lists an open session: "For information: Payobook support opened AB Mauri — started less than an hour ago" |
| Public status page | says nothing about any of it |
| Template scheduled jobs after the update | 0 active (rail R8) |

Screenshots: `docs/handovers/fleet_p6_shots/` (17 files).

## Things the owner should know

- **abm had no recovery account.** It was adopted rather than provisioned, so
  the tenant-admin rails never ran there. `support_open` now makes sure of the
  account before it writes the row — the first live session created it (uid 245,
  `platform.recovery@payobook.com`, no password, no email address).
- **The trail on abm holds three real sessions** from this validation, with
  honest reasons. They are a true record and were left in place.
- **Three `info` alerts** (`support_session:abm`) are on the platform's own
  alert list, resolved. They are not fiction and only *critical* resolved alerts
  ever reach the public page, so they were left rather than deleted (contrast
  F41, which was about invented ones).
- **A browser that has opened a support session remembers the recovery account
  on that customer's login screen** (the framework's "choose a user" list, kept
  in that browser only). It is our own machine, not the customer's, but it is
  worth knowing before a screen-share.
- **One browser, one session.** Opening a support link in a browser that is
  already signed into that customer as somebody else replaces that session. Use a
  separate browser profile if you need to be both at once.

## Open owner decisions

1. **Nothing has been pushed.** P6 added 5 commits; the branch `19.1` is still
   local, as it has been for every programme since.
2. **The rollout of 2026.09.03-6 is finished on all three databases** but its
   canary watch window is still counting. It can be left to close by itself.
