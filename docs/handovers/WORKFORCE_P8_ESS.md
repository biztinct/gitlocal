# WORKFORCE P8 — ESS Workforce: the employee surface, shift acknowledgment, and pulse

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (FULL ledger — now through **W83**; §0
shared-server rules W68/W83 still apply, the parallel pb_hub session may resume).
This phase closes the two P4 descopes (ack + pulse) by building the thing that blocked them:
an employee-facing workforce surface.

## §1 Scope

New module **`pb_ess_workforce`**: a "My Work" section of the existing `/my` portal (Phase-I
pbim-skinned) with **My Schedule + shift acknowledgment**, **My Timesheet + own-punch
regularization**, **My Leave**, **My Overtime** — plus the **token-URL ack** for employees
without logins, the **shift-end pulse** (portal + driver PWA checkout), manager-side **ack
badges** in Schedule and a **Team pulse tile** on Today, and the demo ESS cohort that makes it
all demoable.

**Binding non-goals:** no push notifications (PWA stays app-shell-only); no mobile app; no
changes to approval chains or payroll paths (W12); employee mutations go through EXISTING
state machines (corrections chain, hr.leave) — never a new write path to punches or OT; no
Mission-Control shell changes beyond the Today pulse tile and Schedule ack badges; don't touch
pb_hub/** or docs/handovers/ia/**.

## §2 Verified grounding (P7 report + program records)

- **`pb_me_portal`** extends Odoo's `CustomerPortal` (`controllers/portal.py`;
  `_prepare_home_portal_values` :49-50 disjoint-key counters) — portal-auth. Its Phase-I re-skin
  ships a lean `web.assets_frontend` pbim bundle; follow its template/controller idioms exactly.
- **Token-URL precedent** `pb_formula_studio/controllers/review.py:19` (login-less sign-off) is a
  DIFFERENT mechanism you are introducing to this module — clone its shape: unguessable token,
  single-purpose route, no data exposure beyond the target record, used-token invalidation.
- **Notification precedent** `overtime_request.py:193-197` — `activity_schedule` to the manager
  at submit, `activity_feedback` at decision. The ONLY working pattern; employee-directed
  activities are useless (most employees have no users) — the portal + token URL are the
  employee channels.
- **Demo cohort today:** only the 2 P6 driver logins; the 4,502 general demo employees have
  `user_id = False`. `pb_demo/models/demo_ess.py` exists (Phase-I `ensure_ess_demo_users`:
  manager.demo / employee.demo / minor.demo, passwordless per C18.14). **P8 must seed a wider
  ESS cohort** (§3.6).
- **Driver PWA checkout** (`pb_driver_checkin`, `/driver/check_in_out`) is the natural pulse
  host for drivers; demo drivers carry an open punch daily.
- **Corrections chain** (`hr.attendance.correction`, biz_approval_chain): draft/submitted/
  applied/refused; `_REVIEW_FIELDS` freeze; single sudo writer `_apply()`. P1's I-H3 lesson:
  a request must have its target forced server-side (an employee files only for THEMSELVES).
- **Schedule cockpit** = pb_schedule (P2/P5); Today board = pb_today; both take additive payload
  extensions well (precedents throughout).
- **Chrome validation auth:** the browser's admin session has EXPIRED (P7). The established
  ritual (C18.14 precedent, Phase I): demo logins are passwordless; for validation, set a TEMP
  password server-side (passlib pbkdf2 via odoo-bin shell or SQL — service stopped first, W61),
  validate, then CLEAR the hash and prove it cleared. Use `manager.demo` (backend surfaces —
  verify its groups cover Schedule/Today; report if not) and a seeded ESS portal user (portal
  surfaces). NEVER touch the real admin user's credentials.

## §3 Design decisions (binding)

1. **Module `pb_ess_workforce`** (deps: `pb_me_portal`, `pb_hr_workforce`, `pb_attendance_flow`,
   `pb_timeoff`, `portal`). Portal section "My Work" on the /my home (counter card per the
   `_prepare_home_portal_values` pattern) with four pages, all `auth='user'` + own-employee
   resolution (`user.employee_id`, 404-safe when absent):
   - **/my/work/schedule** — this week + next: shift cards (local wall clock — W63 discipline),
     ack state per shift, "Confirm week" bulk ack; past shifts read-only.
   - **/my/work/timesheet** — the person-week table (reuse the `pb.time.hub.get_person_week`
     CONTRACT but through an own-only gate: new facade method `get_my_week` that forces
     `employee_id = own`, never trusts a param); "Something wrong? Request a fix" per day →
     files an `hr.attendance.correction` for SELF (server forces employee_id; new own-create
     record rule + ACL row — clone the pb_me_portal profile-change security shape incl. the
     I-H3 target-forcing).
   - **/my/work/leave** — balances (pb_timeoff facade, own-scope) + apply (creates own
     `hr.leave` in the normal chain) + my requests list.
   - **/my/work/overtime** — own OT requests read-only (state, hours, bonus split).
2. **Acknowledgment** on `hr.shift.planning`: `ack_state` (`pending`/`acked`), `acked_at`,
   `ack_token` (unguessable, per-shift, generated at publish, invalidated on use/unpublish).
   Publish (single + bulk `publish_shifts`) sets pending + tokens. Channels: portal (button on
   My Schedule, own-shift check), and **token URL** `/work/ack/<token>` (`auth='public'`,
   clone-the-precedent rails: resolves ONLY the token's shift, shows shift summary + Confirm,
   sudo-writes ONLY `ack_state/acked_at` behind a module-level sentinel, expires with the shift's
   start, one-time use). Where the employee has a `work_email`, publish queues a mail (simple
   template, W7 i18n) carrying the token link — mail is best-effort, never blocks publish
   (try/except + skipped-count report, C18.48 discipline: count emails before/after in tests,
   don't storm the live queue — demo employees' emails are @example-style; VERIFY none are real
   and force the mail queue to stay unsent in validation, or seed with no work_email and rely on
   portal+token-page demos).
3. **Manager-side ack visibility**: Schedule cockpit rows get a per-person ack badge for the
   visible week (all-acked green check / "n/m" muted — When-I-Work read-receipt pattern);
   publish-flow toast reports "published N · notified M · no channel K". Additive payload only.
4. **Pulse** `pb.shift.pulse`: `(company_id, department_id, date, rating 1..5, comment optional)`
   — **NO employee link** (true anonymity); double-submit guard via a salted daily hash column
   (`uniq_hash`, unique index; the salt is a system parameter — the hash proves uniqueness
   without identifying; document the privacy contract in the model docstring). Entry points:
   portal My Schedule (prompt appears only after a shift ended today, dismissible), and the
   driver PWA checkout confirmation (5-emoji row — this surface MAY use emoji glyphs as the
   rating control itself, they are the data, not chrome; W3 note it). Aggregation: **Today board
   "Team pulse" tile** — avg + count over 7 days for the current scope, rendered ONLY when
   count ≥ 5 (anonymity floor, refuse below it server-side).
5. **Security rails** (this phase's core risk): every portal read resolves the employee from the
   session user — no employee_id params trusted anywhere; own-only record rules for the new
   ACLs; the ack token writes two fields and nothing else; pulse accepts no employee identifier
   at the RPC boundary; all new mutations ride existing chains as the REAL user (W12). Adversarial
   tests are mandatory (§5 T2): forge another employee's id into every endpoint → refused.
6. **Demo cohort** (extend `demo_ess.py`, idempotent, P6 patterns): ~10 portal users linked to
   Stores-North demo employees (passwordless, adopt-by-name, `is_demo`), plus ack/pulse demo
   states: current week published with a realistic ack mix (most acked, a few pending), ≥6 pulse
   rows over the last 7 days in Stores-North (so the Today tile clears its anonymity floor).
   Rerun-safe; non-demo untouched proofs.
7. **P7 visual-debt sweep**: after establishing the temp-password login, ALSO smoke-check the
   P7 surfaces that went visually unverified: Close board bulk-review UI, grid vi strings (two
   spot translations), deleted legacy menus absent, Pay-Run Payroll Report alive. Screenshot each.

## §4 Work packages (one commit each)

- **WP-1** Portal pages + own-only facades + security rails (+ adversarial tests).
- **WP-2** Ack fields/tokens/publish integration + token-URL controller + mail template
  (best-effort) + portal ack actions.
- **WP-3** Manager-side: Schedule ack badges + publish toast counts.
- **WP-4** Pulse model + portal & PWA prompts + Today tile with anonymity floor.
- **WP-5** Demo ESS cohort + ack/pulse seed states.
- **WP-6** Live validation (temp-password ritual, §2 last bullet) incl. the §3.7 P7 sweep;
  fixes it forces.

## §5 Tests (with features, W9; scoped `-u`; never bare `--test-tags`)

- **T1** Portal pages resolve own employee; user-without-employee → clean 404/empty state.
- **T2 Adversarial:** every new endpoint with a forged employee_id/shift_id/token → refused;
  ack token: wrong token 404, reused token refused, expired refused, token writes only the two
  fields; correction filed via portal has employee forced to self (I-H3); pulse RPC with any
  identity payload → stripped/refused; Today tile below anonymity floor → server returns nothing.
- **T3** Ack lifecycle: publish → pending+token; portal ack; token ack; unpublish invalidates;
  bulk publish counts (notified/no-channel); badge math (n/m, all-acked).
- **T4** Pulse: uniqueness hash blocks a second same-day submission, allows next day; aggregation
  window; floor.
- **T5** Demo seeder idempotency + non-demo untouched (P6-style proofs).
- **T6** Regression: full suite green (the P7 baseline is 380 green — assert no NEW failures).
- **T7–T14 Chrome-MCP live:** portal login as the seeded ESS user → all four pages with real
  data (screenshots `p8_my_*.png`); ack a pending shift → Schedule cockpit badge updates (verify
  as manager.demo); token-ack page start-to-finish in a logged-OUT context (`p8_token_ack.png`);
  pulse prompt after a seeded ended-shift → submit → Today tile reflects it (`p8_pulse_tile.png`);
  driver PWA checkout prompt (`p8_pwa_pulse.png`); the §3.7 P7 sweep screenshots; console clean;
  then CLEAR every temp password hash and prove cleared (psql), mail queue counts before/after
  pasted (no storm), residue policy: seeded demo states STAY, everything else reverted.

## §6 Deploy & verify

Ritual per W10 + W68/W83 foreign-run checks (pb_hub may resume). `-i pb_ess_workforce -u pb_demo,
pb_schedule,pb_today,pb_hr_workforce,pb_driver_checkin,pb_me_portal` + anything touched; version
bumps (W13.1); asset purge expected (frontend bundle); the `--test-enable` no-exit quirk (confirm
in log, kill by PID); Chrome-MCP on https://payobook.com (+ the /my portal and the /work/ack
public route).

## §7 Report back

Commit hashes per WP; T1–T14 evidence (adversarial results verbatim); self-review notes (W0.1);
W-rules appended (re-read the ledger tail first); deviations + reasons; the temp-credential
cleanup proof; and a **wave-closure section**: state of all five closure-report items + the two
descopes now closed, anything still open (e.g. the pb_business_trip-scoped
`hr.workforce.dashboard` deletion follow-up, remaining retired rail records, hoot runner), and
your recommended next work for the owner.
