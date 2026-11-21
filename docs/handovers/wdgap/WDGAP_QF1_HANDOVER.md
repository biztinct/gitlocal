# WDGAP QF1 — Approve several at once in the Approvals inbox; PayAI's daily alerts on Home

Read first: `WDGAP_LEDGER.md`, then `WDGAP_QF1_FACTS.md` (verified plumbing, file:line —
do not re-derive), then `docs/handovers/APPROVAL_MATRIX_LEDGER.md`,
`docs/handovers/workflow2/WF2_LEDGER.md`, `docs/handovers/updates/UPDATES_LEDGER.md` G94–G99.

You are the implementer AND tester/self-reviewer. You do NOT deploy.

## 1. Scope

### A. "Approve selected" in the one Approvals inbox
A1. **Tick boxes on cards that can safely be approved together**, a "Select all on this
    page that I can approve" control, and a tray: "9 of 38 selected · Approve selected ·
    Clear". Clone the selection pattern of `pb_ask_hr/static/src/js/askhr_lens.js:128-134,
    329-357` (selection map over loaded cards only; selections that new filters hide are
    dropped) and the tray of `pb_hr_workforce` `pb_ot_desk.xml:310-312`. The tick box must
    not open the drawer (`inbox.xml:123` whole-card click).
A2. **Which cards get a tick box** — the server decides, per card, in `_card()`
    (`pb_approval_config/models/inbox_facade.py:536-610`): new keys `can_bulk` (Bool) and
    `bulk_why` (short plain reason shown as a tooltip on a disabled box, or empty).
    `can_bulk` is true only when ALL hold:
    - it is my turn (`mine`), the request is waiting and not `blocked`;
    - the process allows it: new Boolean on `biz.approval.process`
      `bulk_ok` ("Can be approved several at once");
    - the process is not a money process (`process.money` false) — hard rule, even if
      somebody sets `bulk_ok` on one (constraint: refuse `bulk_ok` with `money`);
    - I have no conflict on it (I am not the submitter, a maker or the subject where the
      route's independence safeguard is on — reuse `_conflict_kind`, `engine.py:445-452`;
      a request that would need an exception is never bulk).
    Cards that are mine but not bulk-able keep working one by one exactly as today.
A3. **Defaults for `bulk_ok`** (data, set once; `noupdate` semantics so a customer's later
    choice survives upgrades — use a post-migration/hook that sets it only where the field
    is still at its default, do not re-assert on every upgrade): TRUE for `leave`,
    `overtime`, `timesheet`, `correction`, `trip`, `training_request`, `goal_set`,
    `goal_change`, `recognition`, `hr_comm_post`, `letters`. FALSE for everything else
    (all Pay, Money out, Pay data, Setup and Platform processes; every `money` process;
    `resign`, `verdict`, `newhire`, `contract`, `paychange`, `bankchange`, hiring, `generic`,
    `workflow_studio`).
A4. **Server verb** `pb.approval.inbox.decide_many(request_ids)` — approve only.
    Max 50 ids per call (refuse more with a plain sentence). For each id, in its own
    savepoint: re-check `can_bulk` on the server (never trust the client), find MY open
    seat's step key and the request's current lock revision, and decide through the SAME
    engine path the single decide uses (`inbox_facade.decide` → `engine.decide`,
    `engine.py:1182-1308`) with `use_exception=False` — every engine guard stays in force
    (row lock NOWAIT, seat ownership, lapsed delegation, independence, apply-in-savepoint).
    Do not build the heavy `get_request` payload per row. A request that ends `approved`
    with a `block_reason` counts as NOT ok (as `act()` does, `inbox_facade.py:1379-1387`).
    Returns `{results: [{id, ok, title, error}], done, failed}`. Before returning, clear
    the per-request "my turn" cache (`env.cr.cache[('pb_approval_inbox.my_turn', uid)]`,
    FACTS gotcha) so the recount is fresh.
A5. **In-page confirm, then honest results.** Pressing "Approve selected" shows an
    in-page panel (never `confirm()`): "Approve 9 requests?" with the count per kind
    ("6 leave · 3 overtime") and the two primary/secondary buttons. After the call: toast
    "8 approved." and, if any failed, a calm panel listing each failed request with its
    plain reason; failed ones stay ticked, approved ones leave the list. Then `refresh()`
    (`inbox.js:437-439`) so tab counts and cards are right.
A6. Send back / refuse stay one at a time (they need a written reason each).
A7. Keyboard: Space toggles the focused card's box; Escape clears the selection only when
    the tray is showing and no drawer is open (Escape is handled in capture phase —
    `test_static_contract.py:402`).

### B. PayAI's daily alerts appear on Home
Today the alerts are worked out daily but no reachable screen shows them, they carry no
company, and a new row is created every day a condition persists (FACTS B). Fix the
source, then show them.
B1. **Alerts belong to a company.** `payroll.ai.pulse` gains `company_id` (indexed) and a
    multi-company record rule. The four detectors (`payroll_ai_pulse.py:166-385`) run once
    PER COMPANY (loop over companies that have payslips/employees; each detector's
    searches filtered by that company — check how each model carries company: payslips,
    employees, leaves; `hr.payslip.run` has no `company_id`, use the payslips').
B2. **One open alert per thing.** New `dedupe_key` (company + category + department/none).
    If an open (`new`/`acknowledged`) alert with the same key exists, update its figures
    and `write_date` instead of creating another; when the condition no longer holds on a
    run, mark it `resolved` automatically. "Got it" (acknowledge) hides it from Home until
    the figures get worse by a further 5 points or its severity rises.
B3. **Home section** `payai_noticed` in `pb.dashboard.get_home_data()`
    (`pb_dashboard/models/home_data.py:126-220`), read ONLY through `optional('payroll.ai.pulse', …)`
    and registered in `HOME_MODELS` (tests `test_home_data.py:517-535`,
    `test_activation.py:50-60`); add the key to `TOP_KEYS`/`timing` as the tests require.
    Returns `None` (card hidden) when the module is absent, the reader cannot read
    payslips (existing rule, `:453-479`), or nothing is open. Otherwise up to 3 alerts for
    `env.companies`, most severe first (critical > warning > info — sort in Python; the
    selection sorts as text), then newest: `{id, category, severity, direction, pct,
    value, baseline, department, since}`. NO names of people and no stored English title
    in the payload.
B4. **Card "PayAI noticed"** on the Home pulse (`pb_dashboard/static/src/xml/pb_dashboard.xml`,
    in the row of cards at `:244`; `<section t-if=… class="pbd-card">` pattern). Each line:
    a severity dot, a sentence built on the CLIENT from a word table (so it is translated
    in the reader's language — follow `NEEDS` `pb_dashboard.js:152-190` and keep the
    JS-table/server-key parity test `test_home_front.py:116-129` green), e.g. "Pay cost is
    up 14% on the last three months", "Overtime in Production is up 32%", "6 people
    joined this week", "12 leave requests approved in 7 days"; a quiet "Got it" and a
    "Look closer" door. Doors use the existing `door()` helper (`:1681-1698`) to: cost →
    the Insights Explorer; overtime → Workforce insights; headcount → People; leave → the
    Leave Command Center — each only if that action exists (resolve on the server with
    `env.ref(..., raise_if_not_found=False)` and send a `door` key or null; no door, no
    button). Quiet-board rule: no colour unless there is something to act on.
B5. `ic()` returns a new `markup()` each call (FACTS) — compute icons once per load, not
    in the template loop (ledger convention 4, OWL markup flicker).

## 2. Binding non-goals

- No bulk refuse/send back; no bulk for money processes; no exception approvals in bulk;
  no setting screen for `bulk_ok` in the matrix room (report it as a follow-up); do not
  revive or remove the retired `act()` / `get_team_data` verbs.
- No change to the approval engine's decide logic or guards. In `biz_approval_workflow`
  only the new process field (+ its constraint, view field if a process form exists, data).
- PayAI: no new detectors, no change to thresholds, no AI-provider calls added, no change
  to the PDF report, no menu for the old Pulse Alerts list, no on/off switch for the cron.
  Old alert rows (no company) are left as they are and never shown on Home — no data rewrite.
- `pb_dashboard` and `pb_home_hub` must NOT gain a dependency on PayAI or `pb_learn`.
- Do not edit `pb_timeoff`, `pb_ess_workforce`, `pb_me_team`, `pb_explorer`, `biz_access`,
  `pb_pack_*` (other phases are in them).

## 3. Safety rails

R1. Bulk approve can never do what a single approve by the same person could not: it goes
    through the same engine call, per request, as the current user (no `sudo()` around the
    decide), and re-checks eligibility server-side.
R2. One bad request never spoils the rest: per-request savepoint; a lock held by someone
    else ("Someone else is deciding this right now") is a per-row failure, not a crash.
R3. Idempotent per row: pass an idempotency key derived from (uid, request, step, lock
    revision) so a double click cannot decide the next step of the same request.
R4. `test_static_contract.py`: class prefixes `pbam-`/`pbim-` (add `is-sel` to the
    allow-list only if you truly need it — prefer `pbam-…--sel`), kit colour tokens only,
    no `self.env.company` in `inbox_facade.py`.
R5. Alerts never cross companies: record rule + explicit `company_id in env.companies`
    in the Home read; a test with two companies proves it. The headcount detector stores
    names in `details` — Home never returns `details`.
R6. The Home feed must never fail because of PayAI: `section()` savepoint + `optional()`;
    AccessError → hidden card.
R7. Translations: `pb_approval_config` (`vi_VN.po` + `.pot`, full-coverage test
    `test_vietnamese.py:29-65`), `pb_dashboard` (`vi_VN.po` + fresh `.pot`, test
    `test_home_cards.py:200-262`), `biz_approval_workflow` (`vi_VN.po`, `id_ID.po`),
    `pb_payroll_ai_insights` (`vi_VN.po`). PO parse gate. White-label, plain words.
R8. Version-bump every module touched.

## 4. Architecture — exact seams

- `biz_approval_workflow/models/process.py`: `bulk_ok` + constraint; data defaults (A3).
- `pb_approval_config/models/inbox_facade.py`: `_card()` keys; `_can_bulk(request)`;
  `decide_many`. `static/src/js/inbox.js` + `xml/inbox.xml:120-191` + `scss/inbox.scss`:
  selection, tray, confirm panel, results panel.
- `pb_payroll_ai_insights/models/payroll_ai_pulse.py`: `company_id`, `dedupe_key`,
  per-company loop, upsert/auto-resolve, `home_alerts()` (the reader used by Home),
  `rpc_acknowledge_alert` keeps working; `security/`: record rule.
- `pb_dashboard/models/home_data.py`: `_home_payai()` section; `HOME_MODELS`.
  `pb_dashboard/static/src/js/pb_dashboard.js` (+ xml, scss): card, word table, door,
  "Got it" (calls `payroll.ai.pulse.rpc_acknowledge_alert` then removes the line locally).

## 5. Numbered test cases (T = Odoo test; write and run)

`pb_approval_config/tests/test_wdgap_qf1_bulk.py` (fixtures `MatrixCase`, `common.py:15-103`),
`pb_payroll_ai_insights/tests/test_wdgap_qf1_pulse.py`, `pb_dashboard/tests/test_wdgap_qf1_home.py`.

1. T `_card()` gives `can_bulk` true for my-turn leave; false with a reason for: not my
   turn, blocked, money process, process with `bulk_ok` false, I am the submitter under
   independence.
2. T `bulk_ok` cannot be set on a money process (constraint).
3. T Defaults after install/upgrade match A3; a customer-changed value survives a second
   upgrade.
4. T `decide_many` on 3 eligible requests approves 3 and moves each to its next step or
   to done exactly as three single decides would (compare states and seats).
5. T Mixed batch: one eligible, one money, one not mine, one already decided →
   1 ok, 3 failed with plain reasons; nothing else changed.
6. T A row locked by another transaction fails alone; the rest succeed (R2).
7. T Same call sent twice → second call approves nothing new (R3).
8. T 51 ids refused. A non-approver gets failures, never an approval (R1).
9. T After `decide_many`, "My turn" count in the same request is fresh (cache cleared).
10. T Existing suites green: `pb_approval_config` (incl. `test_static_contract`,
    `test_vietnamese`), `biz_approval_workflow`, and the suites of two adapters:
    `pb_timeoff`, `pb_hr_workforce` overtime — `-u` each (ledger G35).
11. T Pulse per company: two companies, a cost jump in one → one alert with that
    `company_id`; a user of the other company reads none (R5).
12. T Dedupe: detector run twice → one open alert, figures updated; condition gone →
    auto `resolved`; acknowledged alert stays hidden from `home_alerts()` until it worsens
    by 5 points or severity rises.
13. T `home_alerts()` order: critical before warning before info; max 3; no `details`,
    no names; old rows without company never returned.
14. T Home payload: section present with an open alert; `None` without payslip-read;
    `None`/absent-safe when the model is missing (simulate through `optional`); existing
    `pb_dashboard` suites green (`test_home_data`, `test_home_front`, `test_home_cards`,
    `test_activation`).
15. Browser, local copy (Claude in Chrome per G99), INSIDE the Home hub: Approvals lens —
    tick 3 leave requests, approve, see results and counts drop; a money request shows a
    disabled box with its reason; keyboard works; Pulse lens — PayAI card shows, "Got it"
    removes a line, "Look closer" opens the right screen; card hidden when nothing is
    open; console clean; phone width.
16. Static gates: py_compile, XML, PO gate, grep the diff for "Odoo" in user-visible
    strings (none).

## 6. Working rules

- NEW git worktree from `origin/19.1`, branch `wdgap-qf1`. Local test recipe: latest
  UPDATES reports + ledger G12, G19, G35, G97.
- Feature-scoped commits (A, B), explicit paths; push `wdgap-qf1`. Do NOT merge. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped" in the report, end with PAUSED.

## 7. Report back — `docs/handovers/wdgap/WDGAP_QF1_REPORT.md` (commit it)

1. What was built; files; version bumps. 2. Test table + full-suite counts.
3. Self-review rail by rail and non-goal by non-goal. 4. Decisions taken (how the A3
   defaults are applied once; door targets found). 5. Owner questions as plain real-world
   questions (e.g. "Which kinds of request should managers be allowed to approve several
   at once? Today: leave, overtime, timesheets, …"). 6. Deploy notes: modules to `-u`,
   tier (new stored fields, a changed daily job → normal; say if risky), the cron touched
   (name), asset purge yes. 7. New gotchas → ledger rows.

Final message to the orchestrator: under 250 words — branch, last commit, test counts,
failures or deviations, owner questions.
