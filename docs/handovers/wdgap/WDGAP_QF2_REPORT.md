# WDGAP QF2 — report: Explorer saved views, Excel download, send regularly

Branch `wdgap-qf2` (from `origin/19.1` at `1065e98bf`). Not merged, not deployed.
Built, tested and self-reviewed by the Opus implementation agent, 2026-11-14.

## 1. What was built

**A. Saved views.** A "Save view" button in the Explorer toolbar opens an in-page card: name,
"Only me" / "Everyone who can open the Explorer". On a view you own it offers "Update this view"
or "Save as new". "My views" and "Shared with me" sit above the starting points in the same card
style; with nothing saved, one grey line: "Save a view to find it here". Own views: open, rename
(inline), share/unshare (one button), delete (in-page "Delete this view?" — warns when its regular
emails stop too). Shared views show "from <owner>" and offer "Save as my own". A view stores the
cleaned question plus the period as a moving starting point when it matches one ("Last month,
moves with the calendar"); a hand-drawn range is kept as "Fixed dates: … to …". Opening re-cleans
the question; a view whose measure/breakdown/filter no longer exists opens on the closest match
with a plain blue note.

**B. Excel.** "Download Excel" next to the CSV Export. Header block (view name or "Net pay by
department", measure, split by, over, period — with "moves with the calendar" for a saved view —
dates, filters in words, made on), then one block per money ("Amounts in VND") with its own Total
row, never a total across monies, then the "Not converted" table; real number cells in the money's
own decimals, frozen header row, widths, the "only the largest 24" note. File name from the
tenant's product name. CSV export is byte-identical to before (shared `_export_rows`).

**C. Send regularly.** On your own saved view, "Send regularly…" opens a right-hand drawer: every
week on a day / every month on day 1–28 / after each pay run is finished; pick people (only active
internal logins with an email who can open the Explorer, in your companies); a live sentence
("Every Monday morning, to 2 people, as an Excel file with a link"). Each schedule card: Send now,
Change, Pause/Resume, Delete (in-page confirm), and "Last sends" (last 10, who, sent / not sent
and why). With no outgoing mail server the drawer says first: "Email is not switched on for this
company, so nothing will be sent yet. The schedule is saved." and each send is written down as
"Not sent — email is switched off". Each person's email is built AS THAT PERSON (their companies,
their divisions), in their language, with a link that opens the view, the Excel attached; queued,
never forced.

### Files (all in `pb_explorer`)

| File | Change |
|---|---|
| `__manifest__.py` | 19.0.2.6.0 → **19.0.2.7.0**; depends + `mail` (already installed through hr); data + rules, cron |
| `models/pb_explorer_view.py` (new) | `pb.explorer.view` (`pbx_save/pbx_update/pbx_delete`, payload, period words); `open_view` on the facade |
| `models/pb_explorer_schedule.py` (new) | `pb.explorer.schedule`, `pb.explorer.schedule.log`, `_cron_send_due`, `_send_one`, `_mark_due_after_run`, drawer facade (`schedule_drawer/save/pause/delete/send_now`) |
| `models/pb_explorer.py` | `_export_rows` (shared), `export_csv` re-based on it, `export_xlsx` + `_xlsx_bytes`, `my_views`, `get_schema()['views']`; `WORDS_LANG` for the four module-level word helpers (see ledger QF2-G2). Still write-free (test_08). |
| `models/hr_payslip_run.py` | mark-due on `write(state='done')` AND `_approval_apply` (super via `getattr`, savepoint + try) |
| `security/ir.model.access.csv`, `security/pb_explorer_rules.xml` (new) | internal users only; views own-or-shared read / own write; schedules owner+recipients read / owner write; log read via its schedule; `base.group_system` all |
| `data/pb_explorer_schedule_data.xml` (new) | cron **"Payobook: send saved Explorer views"**, hourly, `noupdate`, active |
| `static/src/js/explorer.js`, `xml/explorer.xml`, `scss/explorer.scss` | toolbar buttons, save card, view cards (`pb_explorer.ViewCard`), drawer, `#pbxv=<id>` link reader; icons cached (no new `markup()` per redraw) |
| `i18n/pb_explorer.pot`, `i18n/vi_VN.po` | template re-exported (438 entries); 164 new Vietnamese entries |
| `tests/test_wdgap_qf2.py` (new) | 12 tests, T1–T12 |

## 2. Tests

| # | Case | Result |
|---|---|---|
| T1 | save → My views (and first paint); rename; update; unshared invisible; shared visible with owner; non-owner cannot change/delete; Save as my own; delete; empty name refused | PASS |
| T2 | a login without the Explorer gate: all 12 new calls refused | PASS |
| T3 | "Last month" saved 14 Nov → opens as November on 5 Dec, December on 2 Jan; fixed range stays; Everything stays | PASS |
| T4 | junk keys, gone measure/breakdown/filter, a non-dict stored question: opens, plain note, no traceback; not-yours / gone → plain message | PASS |
| T5 | workbook: header block, numeric cells, frozen row; own mode two monies → two blocks, two totals, no sum, VND 0 decimals / USD 2; Not converted table; truncated note | PASS |
| T6 | CSV byte-identical to the pre-change method (golden kept in the test) for 4 real specs + a two-money/unconverted payload | PASS |
| T7 | weekly/monthly due in company time (HCMC, Sydney, fallback UTC+7), week and month-end boundaries, day ≤ 28; cron sends once, same hour again sends nothing; Send now doesn't move the next send; pause | PASS |
| T8 | two readers held to different divisions get different workbooks (2 vs 1 people), even when the caller's context names a company they can't see | PASS |
| T9 | lost access → skipped + line; no email → skipped + line; left the company → skipped; others sent | PASS |
| T10 | no mail server: no `mail.mail`, line "Not sent — email is switched off", no error (Send now and cron); with a server record: one queued (`outgoing`) mail per person, one .xlsx, link `#pbxv=<id>`, no "Odoo"/"odoo" in subject, body or file name | PASS |
| T11 | finishing via `_approval_apply` marks due, approval unchanged; direct `write(state='done')` marks due; mark-due raising → approval still completes; another company's run doesn't mark | PASS |
| T12 | one schedule raising doesn't stop the next (and still moves on — no retry storm); caps 25 people / 20 schedules; nobody without the gate; only the owner schedules; stranger can't read | PASS |
| T13 | suites (local, copy of `am_wf2p6a_base`) | see below |
| T14 | browser | see below |
| T15 | static gates: py_compile, XML parse, PO gate (`polib`: vi 438 = pot 438, 0 missing, 0 "Odoo" in msgstr), diff grep for "Odoo" in user-visible strings: none | PASS |

**T13 suite counts**
- `-u pb_explorer,pb_insights_hub`: **117 tests, 2 failed, 0 errors** (baseline before any change: 105 — the 12 new ones added). Every pb_explorer test is green. The 2 failures are `pb_insights_hub` `test_the_lens_order_matches_the_mockup` and `TestPayrollReportReskin.test_the_feature_set_is_intact` — **already failing on the unchanged code** (baseline run before any change: 105 tests, the same 2 failed). Not fixed, as instructed (FACTS §6).
- `-u pb_explorer,pb_payruns,pb_pay_delivery`: **186 tests, 5 failed, 0 errors**: pb_pay_delivery 29 green; the 5 are `pb_payruns` `TestRunScreen` (close-week checks from `pb_close` data in the local template). **Same 5 fail with the pre-QF2 pb_explorer** (baseline run with the 19.1 copy of pb_explorer first in the path). Not caused by QF2.
- Expected ERROR log lines: three, all from tests that make things fail on purpose (T11 mark-due raising, logged on both paths; T12 schedule raising).
- A first combined run hit "No space left on device" on this Mac (3 errors); re-run in two halves after dropping scratch databases — numbers above are the clean runs.

**T14 browser** (Claude in Chrome, local copy at 127.0.0.1, a seeded 151 MB database — the 2 GB walk copy did not fit on the disk; two analysts held to two divisions; jobs and mail servers off). Standalone and inside Insights › Explorer: saved and shared a view, found it under My views; as the second analyst it appeared under Shared with me "from Walk Analyst One", opened with their own figures ($67.6M South vs $62.4M North), Save as my own, delete with the in-page confirm. Download Excel: file opened with openpyxl — header block, "Amounts in USD", North only, frozen row. Weekly schedule saved, Send now → history "Not sent — email is switched off" for both people, calm blue line at the top of the drawer, Escape closes it. The emailed link (`…/action-pb_explorer.action_pb_explorer#pbxv=17`) opened the shared view for the second analyst. Scrolling inside the hub works. Console: 0 errors throughout. Narrow width: Chrome would not go below 614 px; that is under the 620 px phone breakpoint, so the phone rules ran — no sideways scroll (scroll width = window width), drawer 460 px wide; one squeeze on the shared card's name found and fixed (actions now wrap under the name). True 390 px not checked (iframes refused, window minimum).

## 3. Self-review

**Rails.** R1: every new RPC (`my_views`, `open_view`, `export_xlsx`, the five `schedule_*`, `pbx_save/update/delete`) calls `_require()` first (T2); record rules as specified; ACLs `base.group_user`, nothing for portal. R2: the send builds as `with_user(recipient)` with the recipient's OWN companies set explicitly (see ledger QF2-G1) — T8 proves different divisions → different attachments. R3: the workbook loops parts; each block has its own Total; T5 asserts no cross-money sum. R4: hook in savepoint + try on both paths (T11); per-schedule and per-recipient savepoints (T12, T9). R5: `next_due` written (and committed outside tests) before building; same-hour rerun sends nothing; Send now leaves it (T7). R6: active internal + email + gate + shared company to be offered; skipped and written down at send time; caps 25/20 (T12). R7: stored question re-cleaned on every open and every send; unknown keys dropped on save; plain note (T4). R8: no new `markup()` per redraw (icons cached in `icx`); drawer/cards cloned from existing patterns; `orm.silent` for the background views reload; tested inside the hub and standalone. R9: plain words, Lucide only, all new strings in vi + pot. R10: version bumped; new models have ACLs and rules.

**Non-goals.** No sharing with a role/person (only me / everyone with the Explorer). No "Reports I receive" tab. No edits outside `pb_explorer` (+ docs). No PDF/PNG, no other boards, no external recipients, no measure/dimension/access/currency rule changed (`_clean_spec`, `_where`, `_buckets` untouched). No mail server configured or used — test mail servers exist only inside rolled-back test transactions, nothing was ever sent.

**Deviations / notes.**
- Commits: A, B and C share three files (`pb_explorer.py`, `explorer.js`, `explorer.xml`), so the code is one feature commit rather than three; docs and the report are separate commits.
- Only the view's owner can set up regular sends (a non-owner presses "Save as my own" first) — keeps a schedule from vanishing when someone else deletes their view. Owner question 1.
- Saved views per person capped at 50 (not in the spec; a refusal says so).
- The module-level word helpers in `pb_explorer.py` were touched (a local `context` + a context variable) so emailed workbooks are in the recipient's language and the job does not log a warning per word. Screens unchanged.
- The emailed link uses `/bizapp/…` (biz_deroute installed on every live database); on a database without biz_deroute it would fall back to the platform path.

## 4. Decisions taken

- **Link format**: `#pbxv=<view id>` (same `key=value` shape as the existing `#pbex=` link, which the router leaves alone). The view is re-resolved for whoever opens it, so the link never carries numbers or widens anything.
- **Time**: weekly/monthly at **07:00 company time**; zone = company address time zone → company working-hours time zone (if not UTC) → **Asia/Ho_Chi_Minh (UTC+7)**.
- **After each pay run**: goes out on the **next hourly tick** after the run is finished (not the next morning).
- **"Email switched on"** = at least one active outgoing mail server record on that database (spec C4).
- Email-off sends still count as a send and are written down per person (history shows why), once per due date — no retries.

## 5. Owner questions

1. Should people be able to set up regular emails on a view someone else shared with them? Today only the person who saved a view can; others press "Save as my own" first and schedule their copy.
2. Emails set for "after each pay run" go out within the hour after the run is finished. Is that right, or should they wait for 7 am the next morning?
3. Weekly and monthly emails go at 7 am company time; a company with no time zone set uses Vietnam time. Is that the right default?
4. On payobook.com, is outgoing email set up as a mail server inside the app? If email is only set up in the server's config file, the Explorer will say "email is switched off" there and send nothing.

## 6. Deploy notes (for the deploy agent)

- Module: **`pb_explorer` only**, `-u` on payobook, payobook_template, p0clone, rize, sudima. Never abm.
- Tier: **normal** (two new tables + one new log table, record rules, one new scheduled job; no stored data rewritten).
- New scheduled job: **"Payobook: send saved Explorer views"** (hourly, ships active, `noupdate`). Include it in the cron snapshot before/after.
- Asset purge + `web.assets.version` bump: **yes** (JS/XML/SCSS changed).
- On rize, sudima and p0clone (no outgoing mail on purpose) schedules save, the drawer says email is off, and each send is recorded as "Not sent — email is switched off". Expected; do not raise.
- Read-only check worth doing on payobook: `SELECT count(*) FROM ir_mail_server WHERE active` (owner question 4).
- New tenants: the job is active on the template, so pb_tenants re-enables it on new tenants.

## 7. New gotchas → ledger rows QF2-G1 to QF2-G7 (phase-prefixed so parallel phases cannot clash) (`WDGAP_LEDGER.md`).
