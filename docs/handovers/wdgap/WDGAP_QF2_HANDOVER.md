# WDGAP QF2 — Explorer: named views you can share, Excel download, "send me this regularly"

Read first: `WDGAP_LEDGER.md`, then `WDGAP_QF2_FACTS.md` (verified plumbing, file:line —
do not re-derive), then `docs/handovers/workflow2/WF2_LEDGER.md` D29 (tenant email is off
on purpose) and `docs/handovers/updates/UPDATES_LEDGER.md` G94–G99.

You are the implementer AND tester/self-reviewer. You do NOT deploy.

## 1. Scope (all inside `pb_explorer`)

### A. Saved views
A1. **"Save view"** in the Explorer toolbar (`pb_explorer/static/src/xml/explorer.xml:31-40`):
    name it, choose "Only me" or "Everyone who can open the Explorer". Saving again on a
    view you own offers "Update this view" or "Save as new".
A2. **"My views" and "Shared with me"** shown above the starting views
    (`explorer.xml:109-150`), same card style, quiet when empty (one line "Save a view to
    find it here"). Open, rename, share/unshare, delete (own only; in-page confirm, never
    `confirm()`). A shared view shows who owns it; non-owners can open and "Save as my own".
A3. A saved view stores the cleaned spec PLUS the period as a moving preset when the
    current period matches one (`_resolve_period` presets, FACTS §1 gotcha) — so "Last
    month" stays last month. A custom date range is stored as fixed dates and labelled so.
A4. Opening a saved view runs it through `resolve_spec`/`_clean_spec` again: a view never
    widens what the reader may see (company/division narrowing happens at query time).

### B. Excel
B1. **"Download Excel"** next to the existing export: `export_xlsx(spec)` cloned from
    `pb_payrun_results/models/payrun_results.py:484` (openpyxl in a try; same return
    shape; browser download like `payrun_results.js:296-316`). Layout mirrors
    `export_csv` (`pb_explorer.py:2097`): a header block (view name if any, measure, split,
    period, filters, "made on"), then **one block per currency part** with its own total —
    never a total across currencies — then the "Not converted" table. Real number cells
    with the currency's format, frozen header row, sensible widths, the truncated note
    when series were capped at 24. Filename via `product_label(env)` like `export_csv`
    (:2154) — never a hard-coded brand.
B2. Keep the CSV export exactly as it is.

### C. Send me this regularly
C1. On a saved view: **"Send regularly…"** opens a drawer: how often — `Every week on
    <day>` / `Every month on day <1–28>` / `After each pay run is finished`; who receives
    it — pick people (only logins that can open the Explorer are offered); a preview
    sentence ("Every Monday morning, to 3 people, as an Excel file with a link").
C2. **Each recipient gets THEIR OWN numbers**: the query runs `with_user(recipient)` so
    company/division visibility applies; a recipient who may no longer open the Explorer
    is skipped and noted (FACTS §1: `_require` raises → per-recipient try/except).
C3. **Delivery**: one email per recipient, plain branded-neutral body (view name, period,
    two or three headline lines from the result, a link that opens the view in the
    Explorer), the Excel attached. Built like `pb_demo_portal/models/signup_report.py:135-146`
    (`mail.mail` + attachment), queued — do not force-send inside the request.
C4. **No email on this database is normal** (rize, sudima, p0clone — ledger convention 9).
    When no active outgoing mail server exists: the drawer says so up front ("Email is not
    switched on for this company, so nothing will be sent yet. The schedule is saved.") and
    the run is recorded as "Not sent — email is switched off", never an error, never a
    retry storm. Detect with a search for an active `ir.mail_server`
    (precedent `pb_hiring/models/connections.py:129`).
C5. **History**: the drawer shows the last 10 sends per schedule (when, to whom, sent /
    not sent and why). The owner can pause, change or delete a schedule, and "Send now".
C6. **Mechanics**: model `pb.explorer.schedule` (view, cadence fields, recipients,
    `active`, `next_due`, `last_run`) + `pb.explorer.schedule.log`. ONE hourly cron
    (`noupdate="1"`, Odoo 19 cron fields only — no `numbercall`/`doall`) sends what is
    due, in the company's timezone morning (07:00 local; fall back to UTC+7), stamping
    `next_due` BEFORE sending so a crash cannot double-send. "After each pay run": mark
    matching schedules due from the finished-run hook — clone
    `pb_pay_delivery/models/payroll_journal.py:380-402` (`_approval_apply`, super through
    `getattr`, own work in try/except so an approval is NEVER blocked) AND cover the demo
    path that writes `state='done'` directly (`pb_explorer/models/hr_payslip_run.py`
    already hooks `write()` — extend it). The hook only marks due; the cron sends.

## 2. Binding non-goals

- No sharing with a specific role or person (only "me" / "everyone who can open the
  Explorer"). No "Reports I receive" hub tab. Do NOT edit `pb_insights_hub`,
  `pb_filter_kit`, `pb_insights`, `pb_workforce_insights`, `pb_approval_config`,
  `biz_approval_workflow`, `pb_pack_*`.
- No PDF/PNG download, no download on the other Insights boards, no general report
  builder, no external (non-login) recipients, no change to any measure, dimension,
  access rule or currency rule of the Explorer.
- Do not configure, test-send through, or raise the absence of a mail server anywhere.

## 3. Safety rails

R1. **Access**: every new RPC calls `_require()` first. Record rules on the two new
    models: a view is readable by its owner, or by anyone when shared (the Explorer gate
    still applies in code); writable/deletable by its owner only (`base.group_system` any).
    A schedule is visible to its owner and its recipients (read), writable by its owner.
    ACLs: internal users; no portal.
R2. **Never widen**: scheduled runs use `with_user(recipient)` with NO company override in
    context (FACTS §1: env.companies falls back to that user's own companies). Test with
    two users who see different divisions and assert the two attachments differ.
R3. **Never add two currencies**: the workbook loops `parts` exactly like `export_csv`;
    a test opens the bytes with openpyxl and asserts there is no cross-currency total.
R4. **The pay-run hook cannot block or undo an approval**, and a failing schedule cannot
    stop the other schedules (per-schedule and per-recipient savepoints/try-except).
R5. **No double send**: `next_due` advanced before sending; cron re-run in the same hour
    sends nothing; "Send now" does not move `next_due`.
R6. **Recipients**: only active internal users with an email; a recipient without email is
    skipped and noted. Cap 25 recipients per schedule, 20 schedules per owner.
R7. Spec stored in a saved view is re-cleaned on every use; unknown keys dropped; a view
    whose measure/dimension no longer exists opens with a plain message, never a traceback.
R8. OWL: no new `markup()` per redraw; clone the existing drawer/toolbar patterns in
    `explorer.js`; `orm.silent` for background reads where the file already does so.
    Test the Explorer INSIDE the Insights hub (hub-lens no-scroll trap) and standalone.
R9. White-label, plain words, Lucide icons. Every new string in `pb_explorer/i18n/vi_VN.po`
    and the `.pot` — `test_p7_vietnamese` checks completeness. PO parse gate.
R10. Version-bump `pb_explorer`. New models → `ir.model.access.csv` + rules XML.

## 4. Architecture — exact seams

- `pb_explorer/models/pb_explorer_view.py` (new): `pb.explorer.view` — `name`, `user_id`,
  `shared` (Bool), `spec` (Json), `period_preset` (Char), `sequence`; methods
  `pbx_save`, `pbx_update`, `pbx_delete`, payload builder (clone
  `pb_filter_kit/models/filter_view.py:39-74` + its three rules).
- `pb_explorer/models/pb_explorer.py`: `my_views()` on `pb.explorer` (returns
  `{mine:[], shared:[]}`), included in `get_schema()` (:1716) so the first paint has them;
  `export_xlsx(spec, view_id=None)` beside `export_csv` (:2097); a shared internal
  `_export_rows(spec)` so CSV and Excel cannot drift.
- `pb_explorer/models/pb_explorer_schedule.py` (new): the two models, `_cron_send_due()`,
  `_send_one(schedule)`, `_mark_due_after_run(company)`, `send_now`, facade methods on
  `pb.explorer` for the drawer.
- `pb_explorer/models/hr_payslip_run.py`: mark-due hook (both paths).
- `pb_explorer/data/`: cron. `security/`: ACLs + rules.
- `pb_explorer/static/src/js/explorer.js` (+ `explorer.xml`, scss): toolbar buttons
  (:31-40), My views / Shared with me (:109-150), save dialog, schedule drawer; opening a
  view sets `state.spec` then `run()` (which writes the hash, :265). The emailed link is
  the Explorer action URL plus `#pbex=…` built on the server with the same short keys as
  `HASH_KEY` (:78) — or a `#pbxv-<id>` hash handled in `readHash()` (:590-617) if simpler;
  only plain `#name` style hashes, no query strings.

## 5. Numbered test cases (T = Odoo test; write and run)

`pb_explorer/tests/test_wdgap_qf2.py`, tagged.

1. T Save → appears in `my_views().mine`; rename; update; delete; another user cannot
   edit or delete it; unshared is invisible to others; shared appears in their `shared`.
2. T A user without the Explorer gate cannot call any new RPC (AccessError).
3. T Period preset: a view saved on "last month" resolves to the new last month when the
   clock moves (freeze time); a custom range stays fixed.
4. T A stored spec with a junk key / removed measure opens cleanly (R7).
5. T `export_xlsx`: valid workbook; header block; numbers are numeric cells; own-currency
   mode with two currencies → two blocks, two totals, no combined total; group mode with an
   unconverted currency → "Not converted" table; `truncated` note when capped.
6. T CSV export byte-identical to before for the same spec (golden from the pre-change
   method on the same data).
7. T Schedule weekly/monthly: due computed in the company timezone; cron sends once;
   second cron run same hour sends nothing; `next_due` moves correctly over month ends
   (day 28 rule) and week boundaries.
8. T Two recipients with different division visibility get different figures (R2).
9. T Recipient who lost access → skipped + log line; recipient without email → skipped +
   log line; others still sent.
10. T No active mail server → log "Not sent — email is switched off", no `mail.mail`
    created, no exception; with a mail server record present → one `mail.mail` per
    recipient with one xlsx attachment and no brand name in subject/body/filename
    (assert the word "Odoo" absent).
11. T After-pay-run: finishing a run through `_approval_apply` marks the schedule due and
    the approval result is unchanged; the direct `write(state='done')` path marks it too;
    patch the mark-due method to raise → the approval still completes (R4).
12. T One failing schedule does not stop the next (R4). Caps enforced (R6).
13. T Existing `pb_explorer` suites green, including `test_p7_vietnamese`; `pb_payruns`
    and `pb_pay_delivery` suites green (shared hook) — `-u` each (ledger G35).
14. Browser, local copy (Claude in Chrome per G99), inside the Insights hub and
    standalone: save, find under My views, share, open as a second user, download Excel
    and open it, set a weekly schedule, "Send now", see history; no-mail database shows
    the calm line; console clean; phone width.
15. Static gates: py_compile, XML, PO gate, grep the diff for "Odoo" in user-visible
    strings (none).

## 6. Working rules

- NEW git worktree from `origin/19.1`, branch `wdgap-qf2`. Local test recipe: latest
  UPDATES reports + ledger G12, G19, G35, G97.
- Feature-scoped commits (A, B, C), explicit paths; push `wdgap-qf2`. Do NOT merge. Do
  NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped" in the report, end with PAUSED.

## 7. Report back — `docs/handovers/wdgap/WDGAP_QF2_REPORT.md` (commit it)

1. What was built; files; version bump. 2. Test table + full-suite counts (and whether the
   `pb_insights_hub` lens-order test was already failing before your change — FACTS §6;
   do not fix it, report it). 3. Self-review rail by rail and non-goal by non-goal.
4. Decisions taken (hash format for links, timezone fallback). 5. Owner questions as plain
   real-world questions. 6. Deploy notes: modules to `-u`, tier (two new tables + a new
   scheduled job → normal), cron name (for the cron snapshot), asset purge yes; note that
   on rize/sudima/p0clone schedules save but do not send. 7. New gotchas → ledger rows.

Final message to the orchestrator: under 250 words — branch, last commit, test counts,
failures or deviations, owner questions.
