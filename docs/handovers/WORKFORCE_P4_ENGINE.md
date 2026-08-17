# WORKFORCE P4 — The engine: tolerances, locks, the Close ritual, and the clean batch

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W47**),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockup C — "Close week 33" — is THE visual target for the
Close lens: auto-approved/flagged/missing stat strip, flagged-row table with scheduled-vs-actual
bars and reason chips, day-lock chips, the payroll-handoff rail with checklist + CTA).
Prior phase: P3b's P4 grounding (§2) is measured file:line fact — do not re-derive.

## §1 Scope — and two honest descopes

Build the substance behind the shell: **tolerance classification** (clean vs flagged),
**day/week locks** that actually guard the writers, the **Close-the-week ritual** as a new
Mission-Control lens, a **payroll-run advisory** (the young-worker pattern) surfacing unclosed
weeks, and the dock's **"Approve all N clean"** batch.

**Descoped from P4, by evidence (report them as deferred, do not build):**
- **Employee shift acknowledgment** — there is no employee-facing workforce surface (`pb_me_portal`
  exposes zero workforce data; most demo employees have no `res.users`) and no push plumbing
  (PWA is app-shell-only by design). Ack without a surface is theater. Defer to a future
  "ESS Workforce" phase; the `pb_formula_studio` token-URL sign-off is the noted precedent.
- **Shift-end pulse** — same missing surface. Defer with ack.

**Binding non-goals:**
- **No money-path changes** (W12): the payroll bridges (`_get_formula_input_values` chain) are
  UNTOUCHED. The advisory wraps `pb.payrun.wizard` append-after-super inside try/except and can
  NEVER raise or block (the pb_young_worker cardinal rule). "Est. gross" in the handoff rail is
  display math on `_pb_hourly_rate` only.
- **Do not build punch→OT derivation.** Grounding: nothing on the payroll path reads
  `hr.attendance`; OT hours are grid-entered by design (Sudima B). Locks therefore protect
  `hr.overtime.request` decisions AND punch integrity — not because punches move money, but
  because they are the audit substrate (say this in the module docstring).
- **New code never reads `hr.shift.planning.compliance_status`** (stale-by-construction: stored
  compute over `now()`, no cron, `actual_check_*` never written by production code). The proven
  shape is live derivation (`pb_today.py:295-317`). This becomes a W-rule.
- Don't modify the exception engine's internals; don't touch `biz.approval.chain.mixin`'s state
  machine; don't chase the catalogued pre-existing failing tests.
- No sidebar changes (Close is a lens inside the shell; the rail stays "Mission Control").

## §2 Verified grounding (P3b report — file:line, do not re-derive)

- **Payroll seams:** `_get_formula_input_values` chain = base
  `pb_hr_payroll_formula/models/hr_payslip_formula.py:316` (terminal) ← OT bridge
  `pb_workforce_payroll_bridge/models/hr_payslip.py:27` (reads `hr.overtime.request`
  `state='approved'`, `approved_hours`/`bonus_hours`) ← trip bridge. Bridges are
  MRO-order-unpinned but key-disjoint. The advisory precedent to clone: `pb_young_worker` wraps
  `pb.payrun.wizard`, appends exceptions, never raises; its MRO-outer proof test is test_09.
- **`hr.attendance` has NO state and NO period guard anywhere.** Core write guard only blocks
  foreign-employee moves; `pb_attendance_flow/models/hr_attendance.py:42-58` guards `unlink()`
  via the `_CORR_TOKEN` `object()` sentinel — **there is no matching `write()` guard**. Writers of
  `check_in/out`: direct officer write, the Weekly-Entry grid (`attendance_weekentry.py:509/521`,
  `pb_entry_source='grid'`), the import wizard (`attendance_import.py:341/361`), corrections'
  single writer `_apply()` (`attendance_correction.py:263-304`, sudo + sentinel, approve lands
  `refused` with `apply_error` on failure rather than raising), the driver PWA live punch.
- **Correction states:** draft/submitted/approved("Applied")/refused; `_REVIEW_FIELDS` freeze
  post-draft; `_check_coherent` pins the punch to the correction's day.
- **Grace/tolerance home:** `pb.attendance.rule` (company-else-GLOBAL two-search, ships a global
  default row). Extend it — don't create a parallel config model.
- **OT requests:** hours grid-entered (`attendance_weekentry.py:530`), split at approval by
  `pb.ot.ceiling._split` (`overtime_request.py:199-221`); ceilings RPC payload =
  `get_ot_ceilings` (`:333`); the only notification precedent is `overtime_request.py:193-197`
  (activity to manager at submit, feedback at approve).
- **Dock/act:** `pb.team.act` dispatches via `_ACT_MAP` as the REAL user; `takes_note` derived
  from it (W42); payload additive-extension precedent set in P3b (W45/W46/W47).
- **Lens plumbing:** P3a/P3b lens map in `pb_mission`; host→lens instructions ride the W44 nonce
  (`pb_cmd`); `WfPersonWeek`/drawer available; `_pb_hourly_rate` on `hr.contract` (P2, display
  math). Sidebar icon set is fixed — check `lock` exists before using it for the lens rail icon.
- **pb_demo regenerates historical punches** — lock guards must not break demo regen (§3.2 bypass).

## §3 Design decisions (binding)

1. **Tolerance config = extend `pb.attendance.rule`** with `variance_minutes` (per-punch clean
   threshold vs shift, default 10) and `variance_hours_week` (per-week clean threshold, default
   0.5). Same company-else-global resolution; migration seeds the global row's new fields.
2. **Locks = new model `pb.wf.lock`** in new module **`pb_close`** (deps: `pb_wf_kit`,
   `pb_hr_workforce`, `pb_attendance_flow`, `pb_time_hub`; `mail.thread` for the audit trail).
   Grain: `(company_id, date)` unique, state `locked` (a row IS a lock; unlink = unlock, both
   logged via tracking + explicit `message_post` with the actor and reason — unlock REQUIRES a
   reason string). Gates: create/unlink = payroll manager OR attendance manager; read = officer.
   **Enforcement guards** (friendly ValidationErrors naming the locked date):
   - `hr.attendance` create/write/unlink when the punch's day (old OR new value) is locked;
   - `hr.attendance.correction` `action_approve` on a locked day → the model's own
     refused-with-`apply_error` path (do NOT raise mid-apply); `action_submit` warns earlier;
   - `hr.overtime.request` state transitions (submit/approve/refuse) when the request's date is
     locked;
   - Import wizard commit rows on locked days → flagged as skipped, not written.
   **Bypass:** su-only context key `wf_lock_bypass` (the C2/trip precedent: honored only when
   `env.su`), so pb_demo regen and emergency admin surgery keep working. Document it.
3. **Close facade `pb.close`** (AbstractModel, officer-gated reads):
   `get_close_data(department_id, week_start)` classifies every employee-day of the week LIVE
   (never `compliance_status`): joins shifts + punches + weekentry rows + pending OT + engine
   missing-punch kinds. Buckets: **clean** (|punch vs shift| ≤ variance_minutes AND week |Δ| ≤
   variance_hours_week AND no missing punches AND no pending OT), **flagged** (reason chips:
   `missing_punch` / `missing_checkout` / `variance_over` / `unscheduled_day` / `ot_pending`),
   **reviewed** (see §3.4). Returns mockup C's shape: stat strip counts, flagged rows with
   sched/actual pairs + Δ, day-lock states, handoff totals (Σ hours, OT approved, bonus, est.
   gross via `_pb_hourly_rate` — display only), checklist booleans, `can_lock` (flags==0 or all
   reviewed) and `can_manage_locks`.
4. **"Approve as-is" = model `pb.close.review`** `(company, week_start, employee_id, date,
   kind, note optional, reviewer, reviewed_at)` — marks a flag consciously waived; the facade
   subtracts reviewed flags; rows are kept forever (audit), unlock does NOT delete them. Writer
   gated manager-tier; never your own employee row (self-review of your own variance is refused —
   the P1a `_ot_can_decide` spirit).
5. **Close lens** in `pb_mission` (8th lens, icon `lock`, label "Close", gated like the lock
   gates — hidden for plain officers): mockup C faithfully — verb header "Close week N" + flagged
   pill; day-lock chips Mon–Sun (click to lock/unlock a day, W21 writes in handlers); stat strip;
   flagged table (person+day, sched-vs-actual thin bars, Δ colored, reason chip, actions **Fix**
   → Time lens Exceptions via `pb_cmd`+person, **Approve as-is** → note-optional review dialog);
   right handoff rail (totals, checklist, CTA **"Lock week & send to payroll"** = locks all
   remaining days — enabled only when `can_lock`; when the week is fully locked the rail shows
   the locked state + "Reopen…" requiring a reason); context = dept/week/search.
6. **Payroll advisory** (in `pb_close`, guarded `env.get('pb.payrun.wizard')`): wrap the wizard's
   exception-collection exactly like pb_young_worker (append after super, try/except, NEVER
   raise): for the run's period, append one advisory line per unclosed week ("Week of Aug 11 not
   closed — 7 flags open, 2 days locked") + total. Include an MRO-outer proof test (clone
   test_09's technique).
7. **Dock clean batch** (`pb_team` additive + `pb_mission` dock): OT items gain `is_clean` =
   requested hours == that week's grid-entered hours for the day AND ceiling headroom ≥ requested
   (via the `get_ot_ceilings` payload) AND its day not locked. Dock footer per mockup B: "N more
   are clean — within tolerance, under every ceiling" + **"Approve all N clean"** which loops
   `pb.team.act` sequentially AS THE REAL USER (W12; stop on first error, toast the partial
   result, reload). Only OT participates in v1 (say so in the UI copy: "clean overtime").
8. **W-rules to append** (with your own numbering): new-code-never-reads-`compliance_status`;
   `wf_lock_bypass` su-only; locks-protect-audit-substrate-not-money (the §1 rationale).

## §4 Work packages (one commit each)

- **WP-1** `pb.attendance.rule` tolerance fields + migration + tests.
- **WP-2** `pb_close`: `pb.wf.lock` + ALL enforcement guards + bypass + tests (this is the
  phase's security core — test every writer path locked AND unlocked AND bypassed).
- **WP-3** `pb.close` facade + `pb.close.review` + tests (classification matrix incl. reviewed
  subtraction, self-review refusal, cross-company scope, gate).
- **WP-4** Close lens in `pb_mission` (+ lens gating) wired to WP-3; Fix/Approve-as-is/lock
  chips/CTA/reopen.
- **WP-5** Payroll advisory + MRO-outer proof test.
- **WP-6** `is_clean` + dock clean batch + tests.

## §5 Tests (with features, W9; scoped `-u` always)

- **T1** Tolerance resolution (company beats global; defaults seeded by migration).
- **T2** Lock guards: punch create/write/unlink blocked on a locked day (both old- and new-date
  paths), fine on unlocked; grid save refused on locked day; import rows skipped-with-flag;
  correction approve on locked day lands `refused` + `apply_error` (not a raise); OT
  submit/approve/refuse blocked when its date is locked; `wf_lock_bypass` works ONLY under
  `env.su`; unlock requires a reason and posts it.
- **T3** Close classification matrix: clean / each flag kind / reviewed subtraction / unscheduled
  day / pending OT; `can_lock` flips; self-review refused; non-officer AccessError.
- **T4** Advisory: appends per unclosed week, silent when all closed, NEVER raises (exception
  injected → swallowed), MRO-outer proof.
- **T5** `is_clean` truth table (hours match / ceiling headroom / locked day) + batch approve
  approves exactly the clean set as the real user.
- **T6** Static gates: no `compliance_status` reads in `pb_close`/new code (grep gate); W16/W21
  (lock chips + CTA + batch write only from handlers); W1/W2/W3; z discipline.
- **T7** Regression: all suites green, no NEW failures (incl. pb_team, pb_mission, pb_schedule,
  pb_time_hub, pb_today, pb_hr_workforce, pb_attendance_flow, pb_wf_kit).
- **T8–T15 Chrome-MCP live:** Close lens renders for a seeded week (seed on demo employees: one
  variance-over day, one missing punch-out, one pending OT — via existing seams); stat strip
  matches SQL; Fix lands on Time·Exceptions with the person pinned; Approve-as-is clears exactly
  one flag and survives reload; lock one day → chip flips, then attempt a punch edit on that day
  via the Time grid → friendly refusal visible; CTA disabled while flags remain → review them →
  CTA enables → lock week → handoff rail shows locked state; Reopen demands a reason and posts it
  (verify chatter row); dock shows the clean-batch footer with N ≥ 1 seeded clean OT → "Approve
  all" approves them (DB-assert) ; screenshots `p4_close_board.png`, `p4_close_locked.png`,
  `p4_lock_refusal.png`, `p4_dock_clean.png`; console clean.
- **T16** Residue zero: every seeded row (punches, OT requests, reviews, locks, chatter) removed
  with before/after counts pasted; pre-existing pending approvals untouched.

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-i pb_close -u pb_wf_kit,pb_hr_workforce,pb_attendance_flow,pb_time_hub,pb_team,pb_mission,pb_schedule,pb_today`,
version bumps everywhere touched — migrations need them, W13.1; asset purge fallback; W33 tell;
no bare pkill; no daemon-reload). Chrome-MCP on https://payobook.com (/bizapp prefix).

## §7 Report back

Commit hashes per WP; T1–T16 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; the two descopes (ack, pulse) restated with their evidence for the owner's roadmap; and a
**program-closure section**: the final state of the Workforce section (lenses, models, guards),
the complete W-ledger count, anything left deliberately un-deleted (legacy files/actions and the
retired 900-band), and your recommended next bodies of work (ESS Workforce for ack/pulse; legacy
dead-code deletion pass; the pb_demo repo↔server sync P2 flagged; anything else you saw).
