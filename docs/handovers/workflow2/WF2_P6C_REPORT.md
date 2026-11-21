# WORKFLOW-2 · Phase 6c report — time off "Sent back" and "Ask again" (D36)

**Status: BUILT, NOT LIVE.** Branch `wf2-p6` (pushed 20 Nov, not merged into 19.1). Nothing deployed, no server touched. Hashes are after the rebase onto `origin/19.1` on 20 Nov.

## 0. In plain words (for the owner)

- When a manager **sends back** a time-off request, the employee's own pages now say **"Sent back"** (amber, not the red "Refused"), show the manager's reason, and say "It was not refused, and no days were taken".
- A button **"Ask again"** opens the normal request form already filled in (kind of leave, days, morning/afternoon or times, note). The person changes what is needed and sends it. It is a **new** request and goes through every normal check (balance, overlap, notice). Documents are not copied, and the form says so.
- The two requests point at each other ("Asked again after the request for 7 Dec was sent back" / "Asked again on 20 Nov"). Each sent-back request can be asked again **once**; then its button disappears.
- Staff see the same on the Time off screen: a **"Sent back"** tab next to "Refused" (which now shows only real refusals), the reason under the chip, and their own "Ask again" that fills in the "Apply for" box.
- The standard time-off form still says "Refused" in its status bar (as you accepted) but has one plain line on top: "Sent back to the employee, not refused: <reason>".
- English, Vietnamese and Indonesian. Nothing about balances or the status changes.

## 1. Commits, versions

| Commit | What |
|---|---|
| `4a0eab5e8` | `pb_timeoff`: the mark, Ask again (staff), cockpit card/filter/view, form note, My requests row, post-migrate, vi/id, 12 tests |
| `0ae1126cb` | `pb_ess_workforce`: My Leave chip + reason + Ask again + filled-in form, vi/id (first `id_ID.po`), 6 tests |
| `1b2c09960` | Browser proof: `tools/workflow_studio/ui_fixture_p6c.py`, `chrome_test_p6c.cjs`, 27 screenshots in `p6c_screens/` |
| (this file) | Report |

Versions: `pb_timeoff` 19.0.1.12.0 → **19.0.1.13.0** (new columns + migration); `pb_ess_workforce` 19.0.1.4.0 → **19.0.1.5.0** (views). No other module changed. `pb_me_portal` untouched (extended by inheritance from `pb_timeoff`, ledger G76).

## 2. Per surface

**The mark (`pb_timeoff/models/leave_sent_back.py`, `hr_leave_approval.py`).** `hr.leave.pb_sent_back` (Boolean, stored, readonly, never cleared) is written in `HrLeaveApproval._approval_return` right after the existing `action_refuse()`. State and balances untouched; the request is still `refuse`. Screens say "Sent back" only while **state = refuse AND the mark** (`_pb_is_sent_back`), so a request an officer moves back to waiting reads as waiting. The reason is read where it already is (`_pb_sent_back_note`, the approval request's `return_note`).

**Ask again link.** `hr.leave.pb_again_of_id` (Many2one, stored) on the new request; `pb_again_id` (computed, by search) on the old one. Every door goes through `hr.leave.create` → `_pb_check_ask_again`: old must be sent back, same employee, not asked before; plus `UniqueIndex (pb_again_of_id) WHERE NOT NULL` as the backstop for a double submit. One internal note on the old request ("Asked again as a new request (dates)").

**Employee — My Leave (`/my/work/leave`, `pb_ess_workforce`).** Row: amber `Sent back` chip, "Your approver sent this back to you. It was not refused, and no days were taken." + the reason in quotes, primary "Ask again" button (`/my/work/leave?again=<id>#pbew-ask`). The link lines ("Asked again after…" / "Asked again on…") jump to the other row (`:target` highlight). Ask again = the **existing** QF3 request form (R2/R2a), filled in server-side (works with scripts off), with a banner (reason, "Documents are not copied…", "Start an empty request instead") and a hidden `again_of`. `apply_leave(..., again_of=)` only adds the link after an ownership check; every QF3 rule runs. Flash: "Asked again. Your new request is waiting for approval."

**Employee — My requests (`/my/requests`).** Override of `pb.me.home._my_requests_rows` in `pb_timeoff`: a sent-back time-off row reads **"Sent back — your turn"** (tone `act`, the expenses/trips "your turn" look) until asked again, then **"Sent back — asked again"** (quiet). Its link goes to the row on My Leave.

**Staff — Time off cockpit (`pb_timeoff`).** Card chip "Sent back" (the Approvals inbox's amber), reason box under it, link lines (open the standard form), and "Ask again" on a sent-back card not yet asked again → the existing "Apply for" drawer filled in (person, kind, days, note) with a banner; `apply_on_behalf(..., again_of=)` creates as the real officer (all rules), keeping the half day / times "as before" when the kind and days are unchanged (the drawer has no control for them). Filter panel: new status value **Sent back**; **Refused** = state refuse AND not marked. New saved view **"Sent back"** right before **"Refused"**.

**Standard form.** One `alert-warning` line from `pb_sent_back_note` + the two link fields when set (`views/hr_leave_sent_back_views.xml`). Status bar, list and board unchanged (still "Refused").

**Email.** Unchanged — the P5a sent-back email stays the only one (its button for an employee-home login goes to `/my/requests`, where the row now says "Sent back — your turn").

## 3. Counts changed (item 4)

| Where | Before | After |
|---|---|---|
| Cockpit filter panel, Status › Refused (count + domain) | all `refuse` | `refuse` and not sent back |
| Cockpit filter panel, Status › Sent back | — | new: `refuse` and sent back |
| Cockpit saved view "Refused" (tab count) | all `refuse` | real refusals only |
| Cockpit saved view "Sent back" | — | new |
| My requests buckets (`/my/requests` tabs + "N waiting on you") | sent back counted under Done | under **Waiting on you** until asked again, then Done |

Not changed (checked): cockpit KPI "Waiting for approval", employee-home leave card (`booked_pending` = waiting states only), My Leave balance tiles, `get_my_counters`. No other screen of ours counts refused time off (grep over `pb_*`/`biz_*`).

## 4. Backfill (post-migrate `19.0.1.13.0/post-sent-back.py`)

Marks a request only when it is `refuse` **and** its latest approval request (highest attempt, then id) is `returned`; logs the count before writing; idempotent (`pb_sent_back IS NOT TRUE`). Local results: `wf2p6c` **0**, `wf2p6c_ui` **0**, `wf2p6c_at` **0** (these copies hold no refused time off at all). Behaviour proven by test 12 (a sent-back one marked, a turned-down one not, second run marks 0). Read-only pre-count for live (run before the upgrade, report per DB):

```sql
WITH latest AS (SELECT DISTINCT ON (r.res_id) r.res_id, r.state FROM biz_approval_request r
                WHERE r.res_model='hr.leave' ORDER BY r.res_id, r.attempt DESC, r.id DESC)
SELECT count(*) FROM hr_leave l JOIN latest ON latest.res_id=l.id
WHERE l.state='refuse' AND latest.state='returned';
```

## 5. Tests

Same database copy (`wf2p6c_before` = `wf2p6_base` + `pb_ess_workforce` installed, which the base lacked), `-u pb_timeoff,pb_ess_workforce --test-tags /pb_timeoff,/pb_ess_workforce`:

| | Before (HEAD `5ba665483`, `wf2p6c_bt`) | After (`wf2p6c_at`) |
|---|---|---|
| pb_timeoff | 101 run, 0 failed, **6 errors** (all `TestLeaveRules`, G60) | 113 run, 0 failed, **same 6 errors** |
| pb_ess_workforce | 126 run, 0 failed, 0 errors | 132 run, 0 failed, 0 errors |
| Total | 227 / 0 / 6 | 245 / 0 / 6 |

Also after: `pb_me_portal` `TestMyRequestsModel` + `TestMyRequestsPage` **9/9**; P5a/P2b time-off message suites pass inside the pb_timeoff run (and 20/20 through `run_p5a.py` together with `TestMyRequestsModel`; the `HttpCase` class cannot run in a shell, G93).

New tests — `pb_timeoff/tests/test_wf2p6c_sent_back.py` (12): mark on send back only (not on engine turn-down, not on cockpit refuse), mark read only while refused; cockpit card en/vi/id; Refused/Sent back counts and view order; form note en/vi/id; My requests row en/vi/id before/after; staff Ask again links both ways + once only; refusals (not sent back, other person); **over the balance → hr_holidays' own rule refuses, nothing linked**; half day kept; backfill + idempotence. `pb_ess_workforce/tests/test_wf2p6c_ask_again.py` (6): row labels en/vi/id for an internal and an employee-home login; prefill; ask again linked once (both logins); balance rule runs; someone else's request refused; HTTP pass for an employee-home login (page, filled form, scripts-off POST).

Static gates: `py_compile`, XML well-formed, PO gate (`PoFileReader`, 0 failures; unique msgids pb_timeoff vi 155→181, id 40→66; pb_ess_workforce vi 258→275, id new 17), no "Odoo" in any new user-visible string or msgstr.

## 6. Browser proof (local, port 8089, Playwright + Chrome)

`P6C_BROWSER_OK`, console clean, 21 checks, 27 screenshots in `p6c_screens/` (all looked at). Per language (en/vi/id): `_1` sent-back row at 390 px, `_1b` My requests "your turn", `_2`/`_2b` Ask again form filled in (morning → afternoon changed, live "after this request" line), `_3` new request waiting + old "Asked again on…", `_3b` link lands, `_3c` My requests after, `_4` staff "Sent back" view. English also `_5` staff Ask again drawer, `_5b` toast + card "Asked again on…", `_6` standard form note; plus a check that the plain "Apply for" drawer still opens without the Ask again box.

Found and fixed during the run: the drawer showed "Choose…" for the kind (options had no selected binding); the first fix used `String()` in the OWL template and crashed the cockpit (G-new below).

## 7. Deviations

1. **Two new stored columns, not one**: `pb_sent_back` (the mark, as the handover says) **and** `pb_again_of_id` (the link Ask again needs for "once" and "both ways"), plus the unique index. Dumps are needed anyway.
2. **`pb_ess_workforce/i18n/id_ID.po` created** (first Indonesian file of the module) holding only the new sentences — the run's rule is vi + id for every new string; QF3 had avoided creating it. The rest of My Leave stays English for Indonesian readers, as before.
3. The prefill puts `selected` on the half-day `<option>`s, which split two existing translated template terms; their Vietnamese was carried to the new split terms (+ Indonesian). Old entries stay in the file (unused).
4. The staff "Apply for" drawer's kind list got a `selected` binding (needed for the prefill to show). Plain "Apply for" behaves as before (checked in the browser).
5. Not built (not in the handover; offer): a "Needs you" line on the employee home ("1 time-off request sent back — ask again"), as expenses and trips have.
6. My Leave still says "Waiting approval" (not D22's "Waiting for approval") for waiting rows — pre-existing, untouched (R1).

## 8. Overlaps found (R2a)

None new. Reused: the QF3 request form and its rules (employee), the existing "Apply for" drawer (staff), the P5a sent-back email (no second email), the inbox's "Sent back" amber. Studio's time-off contract still maps "returned → refuse" — correct, as the status is unchanged.

## 9. Gotchas (proposed ledger rows)

See §10.

## 10. For the ledger / closeout

**D36 row:** | D36 | Time off "sent back" (closeout item 6) | **Label + Ask again** (P6a §7 options B + C, owner 16 Nov): a stored mark (`hr.leave.pb_sent_back`), never a status; "Ask again" = a new request filled in from the old one through the normal doors, linked both ways, once. No workflows on pay runs for now. |

**Phase row:** | P6c | Time off "Sent back" label + "Ask again" (D36) | `WF2_P6C_HANDOVER.md` | built 20 Nov (pb_timeoff 19.0.1.13.0, pb_ess_workforce 19.0.1.5.0; 18 new tests; browser en/vi/id) — `WF2_P6C_REPORT.md` |

**Gotchas:**
- G91 · OWL templates evaluate in the component's context: a global like `String(x)` compiles to `ctx.String` and throws "ctx.String is not a function" **at render**, taking the whole cockpit down. Use `'' + x` (or a component method).
- G92 · A `t-att-*` on an `<option>` (or any inline child) splits the surrounding QWeb translation term: the old combined term's translation silently stops applying. Diff the view's terms before/after (`arch_db` field `get_trans_terms`) and carry the old words to the new terms.
- G93 · `--test-enable … --no-http` still binds `http_port` when the suite has an `HttpCase` (a local server on that port then fails "Address already in use"), and an `HttpCase` cannot run in an `odoo-bin shell` runner (no httpd). Run them through `--test-tags`.
- G94 · `createdb -T` copies no filestore: asset bundles of the clone 500 ("No such file") and the backend hangs on "Opening your workspace". Purge `/web/assets/%` attachments on every clone before browsing; the first backend load then takes >30 s.
- G95 · A local copy's website offers only English, so employee-home pages ignore the login's language (extends G82). The P6c fixture adds vi/id to the local website. Live databases: check `website.language_ids` if a translated employee page shows English.
- G96 · `.pbme-badge` is `text-transform: capitalize`: `innerText` reads "Sent Back" / "Waiting Approval"; compare case-insensitively in browser tests.

**Closeout §3 item 6 text:** "Time off sent back — **built in P6c** (D36: label + Ask again), not live yet. A sent-back request carries a mark (still refused underneath, no day held); our own pages say "Sent back" with the reason; "Ask again" makes a new, linked request through the normal form, once. Standard form/list/board keep "Refused" plus one plain line on the form."

## 11. Go-live (with 6b in one outage if ready; procedure of the 6b handover §4)

- **Modules:** `-u pb_timeoff,pb_ess_workforce`. Cascade (G29): `pb_timeoff` brings `pb_ess_workforce`, `pb_leave_setup`, `pb_mission` and their dependents (e.g. `pb_time_pay`) where installed; `pb_ess_workforce` only where installed (check `ir_module_module` per DB first). `pb_me_portal` needs no `-u` (code-only inheritance).
- **Databases:** payobook, payobook_template, p0clone, rize, sudima. **Never abm.**
- **Before:** read `/opt/deploy-notes.md`, START line, lock; **pg_dump all five** (new columns + unique index on `hr_leave`); run the §4 pre-count SQL per DB and note it; snapshot active cron ids.
- **After:** per DB `INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` (JS/SCSS/OWL changed), restart, warm. Check `latest_version` = 19.0.1.13.0 / 19.0.1.5.0, the migrate log line "pb_timeoff P6c: N … marked" equals the pre-count, cron ids unchanged, hashes match.
- **Stored values:** the new field labels/help and the unique-index message are `model:` entries loaded by the `-u` itself; template terms load with the `-u`. Nothing to write by hand.
- **Live checks (read-only, never create/approve/send):** a sent-back request (if the pre-count found any) shows the chip on the cockpit "Sent back" tab; `/my/work/leave` renders for the QA login.
- Mail: no new email; rize/sudima/p0clone mail stays off on purpose.
