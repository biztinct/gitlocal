# ETP — Expenses, business Trips and Project time on My Payobook — program doc

Owner brief (2026-10-16, after TIERS closed): "continue this work by implementing expenses, business trips and
project timesheet entry on the portal which is a new work. … Ensure the UI should be premium and intuitive and
user friendly. For eg time sheet entry should allow user to enter for the week in one screen in table format
unless you have other better design."

Owner decisions (2026-10-16, AskUserQuestion, asked once — do not re-ask): **phased workflow** (Fable designs,
Opus builds in-session, Fable deploys payobook-first and walks); **all three pieces in the first release**.

Predecessor: TIERS (`docs/handovers/tiers/`), whose rules T-R1…T-R12 and ledger rows T1–T37 bind here too. Every
employee — portal login (share user) or full account — uses these pages; nothing here is "staff only".

## The finding in one paragraph (surveys 2026-10-16, file:line in the handovers)
All three backends exist and are installed on all five databases: stock `hr_expense` 19.0.2.1 (expense sheets are
GONE in 19 — each expense is approved on its own; no portal controller; no approval route in the shared engine; an
expense submitted by someone without a manager user is **auto-approved** by stock — 12 of the 20 portal-login
employees on payobook would be), `pb_business_trip` 19.0.1.2.1 (a full backend trip request with a live engine route
`trip` on payobook: Their manager → Finance approver → HR lead; no portal page), and stock `hr_timesheet` 19.0.1.0
(81,984 lines but 81,622 are automatic public-holiday lines on "Internal"; **not one hour has ever been entered by
hand** in the last 60 days; portal users hold no right on timesheet lines; CE 19 has no week grid and no
validation — `timesheet_grid` is Enterprise and uninstallable here). pb_me_portal already hides the stock
`/my/timesheets` / `/my/projects` / `/my/tasks` customer cards from employees and owns the home registries.

## What the product becomes
| Page | Who | Hero moment | Backend truth |
|---|---|---|---|
| **Expenses** `/my/expenses` | every employee | *Snap a receipt, type the amount, send* — one claim in under thirty seconds from a phone; the receipt image is the card. Several receipts may ride in one claim. | New `pb.expense.claim` (one approval for 1..N stock `hr.expense` rows) approved through the shared engine, process key `expense`; finance then pays through stock Expenses as today. |
| **Business trips** `/my/trips` | every employee | *A live trip card* that rewrites itself as you type (destination, dates, days, allowance, advance) and after sending becomes the approval stepper. | Stock `pb.business.trip` created and sent under sudo after the ownership guard; the existing `trip` route; receipts after the trip go through Expenses with the trip named. |
| **Project time** `/my/project-time` | every employee | *The week on one screen*: a spreadsheet-feel grid, projects down, Mon–Sun across, totals both ways, arrow keys, autosave, "Copy last week"; on a phone, one day at a time. | Stock `account.analytic.line` written under sudo after the ownership guard; no new table; a per-company switch; no approval step in this release. |

## Phases (run in parallel — independent modules, separate clone databases)
| Phase | Agent | Module (new, auto-install) | Clone DB · port · staging | Handover |
|---|---|---|---|---|
| **E1 Expenses** | Opus | `pb_me_expense` (depends pb_me_portal, hr_expense, biz_approval_workflow) | `p0clone` · 8099 · `/tmp/deployE1` | `E1_HANDOVER.md` |
| **E2 Business trips** | Opus | `pb_me_trip` (depends pb_me_portal, pb_business_trip) | `p1clone` · 8098 · `/tmp/deployE2` | `E2_HANDOVER.md` |
| **E3 Project time** | Opus | `pb_me_project_time` (depends pb_me_portal, hr_timesheet) | `p2clone` · 8097 · `/tmp/deployE3` | `E3_HANDOVER.md` |
| **E4 Deploy + walk + close-out** | Fable | — | payobook first, then the batch | `ETP_CLOSEOUT.md` |

pb_me_portal is **not edited by any phase agent**: Fable pre-added the three tiles, their words (EN + VI) and the
three Lucide glyphs (`receipt`, `plane`, `clipboard-list`) in `pb_me_portal 19.0.3.4.0` before launch, so the
three builds never touch the same file. Each phase module draws its own home tile the way pb_ask_hr does.

## Status
- **2026-10-16 ~12:05 Sydney: PROGRAM COMPLETE — E1–E3 live on all five databases**, owner's live walk done on
  payobook as ess2.demo, batch deployed; see `ETP_CLOSEOUT.md`.
- 2026-10-16 10:30 Sydney: surveys done, program + ledger + three handovers written, pb_me_portal 19.0.3.4.0
  pre-work committed, clone databases p1clone/p2clone created from p0clone (dump/restore + filestore copy),
  three Opus agents launched.

## Verified plumbing shared by every phase (do not re-derive; checked 2026-10-16)
- Page skeleton, hero, breadcrumbs, `?done=`/`?error=` flashes, icons, bundles, tests, PO rules, My requests
  vocabulary: `ETP_LEDGER.md` rows E1–E12 (portal architecture survey).
- Controllers extend `PbMePortal` (`pb_me_portal/controllers/portal.py:52`); `_ess_employee()` `:55-64` (sudo search
  on `user_id`, current company first), `_ess_own_employees()` `:66-77`. No route accepts an `employee_id`.
- Portal-only detection: `res.users._pb_portal_only()` (`pb_me_portal/models/ess_landing.py:105-142`); controllers
  never branch on `share` (`portal.py:17-18`) — every page serves both kinds of login.
- Upload precedent (the one to clone): `pb_me_portal/controllers/portal.py:41-42` (`_UPLOAD_MIME_OK`,
  `_UPLOAD_MAX_BYTES` 10 MB) and the handler `:380-445`: bounded read `upload.read(MAX+1)`, mimetype check, sudo
  `ir.attachment` create, record create in a savepoint, attachment bound to the record after it exists.
  Multi-file: `pb_ask_hr/controllers/portal.py:59-90` (`files.getlist`, max 3). pb_training's `_tr_upload` has no
  cap — do not clone it.
- Tokened links for share users (ledger T14/T20): `/web/content/<att>?download=true&access_token=<att.generate_access_token()[0]>`;
  images `/web/image/<att>/<w>x<h>?access_token=` (verify in an HttpCase as the share user).
- Home hooks (`pb_me_portal/models/pb_me_home.py`): `_pbme_extra_cards(emp)` `:315-326` (list of
  `{'key','template','data'}`; precedent `pb_me_portal_comm/models/pb_me_home.py:15-30`); `_pbme_needs_extra(emp, put)`
  `:707-718`, `put(key, n, url, label=, sub=, icon=, tone=, sentence=)` (precedent `pb_ask_hr/models/pb_me_home.py:20-38`);
  `_my_requests_sources()` `:726-849` (dict per source: `key, model, label, icon, employee_field, date_field,
  state_field, states={value: (label, tone)}, url(rec), title(rec)`; precedent `pb_ask_hr/models/pb_me_home.py:40-57`);
  tones `act / wait / ok / no / off` (`:74-76`). Home tile: inherit `portal.portal_my_home`, xpath
  `//div[hasclass('o_portal_docs')]`, `t-call="portal.portal_docs_entry"` guarded `t-if="pbme_home"`
  (`pb_ask_hr/views/portal_templates.xml:28-39`).
- Week start is Monday everywhere (`pb_ess_workforce/models/ess_workforce.py:122-125` `_monday`).
- Tests on a clone (ledger M31 shape): `--addons-path=/tmp/deployEx,/odoo/odoo-server/addons --http-port=<port>
  --db-filter='^<db>$' --workers=0 --max-cron-threads=0 -i <new module> -u pb_me_portal --test-enable
  --test-tags /<new module>,/pb_me_portal --stop-after-init --logfile=` (empty, stdout redirected from a root
  shell into `/home/ubuntu/<name>.log`, ledger T17), launched detached with `systemd-run`.
