# SUDIMA Phase L — Third Approval Tier (Officer → HR → Finance) + Chain Hardening

**Scope item:** #14 Payroll Approval Workflow (*Present, config extension*): the scope names a 3-tier chain Officer→HR→Finance; today the chain is 2-tier (HR→GM). While mapping the chain, review found the entire chain is **enforced only by button visibility** and the cockpit submit seam **skips the HR tier** — Phase L closes both.
**Modules:** `pb_payruns` (state + gates), `pb_approval` (cockpit + RPC), `pb_payrun_wizard` (submit seam), `pb_sidebar` (data). **NO edits to `om_hr_payroll`** — the legacy base stays untouched (selection extended via `selection_add`).
**Ledger:** C1, C2, C18 binding — esp. C18.17 (one-permission-world), C18.40, C18.47/48 (live Gmail SMTP — NO new mail sends), C18.53 (manifest assets → full restart), C18.55.
**Prerequisites:** none (independent of G–K/M). Small phase — expect a modest diff.

---

## 1. Scope

1. **Insert the Officer tier**: `draft → level0 (Officer) → level1 (HR) → level2 (Finance/GM) → done`, with `cancel` reachable from any pending tier.
2. **Enforce every tier server-side** (the found hole): first-line group gates on the `pb.approval` RPCs *and* inside the advance methods — visibility computes stop being the only guard.
3. **Fix the submit seam**: cockpit "Submit for approval" routes a draft run into `level0` via `done_payslip_run` (today it jumps straight to `level2`).
4. **Cockpit WOW uplift** (C18.42 — the surface is touched, so it gets upgraded): 3-lane pipeline board on pbim tokens + Lucide, per-card chain stepper, reject-with-reason.
5. **VI i18n** — the module currently has zero translations.

### Binding non-goals
- **NO configurable chain length/tiers** — 3 fixed tiers; the STAGE dict stays a code-level map (the scope calls it a configuration extension, not a workflow engine; `biz_approval_chain` is NOT retrofitted here — hr.payslip.run predates it and downstream contracts key on its states).
- **NO new mail notifications** for the new tier (C18.47/48 — live Gmail SMTP with an active queue cron; the existing GM notify at level1→level2 stays as-is).
- **NO renaming of existing state KEYS** (`level1`/`level2`/`done` are downstream contracts); relabels happen in cockpit strings only.
- **NO payslip-level state changes** — slips are confirmed once at chain entry (existing behaviour); the Officer tier moves only the run.

---

## 2. Verified plumbing facts (do not re-derive; personally verified 2026-07-24)

- ✓ **State selection** `hr.payslip.run.state`: `draft / level1 ('HR Manager pending') / level2 ('General Manager pending') / done / cancel` — `om_hr_payroll/models/hr_payslip.py:970-976`. `index=True, readonly=True, copy=False, default='draft'`.
- ✓ **Chain entry**: `done_payslip_run()` (:1005-1008) confirms every slip (`line.action_payslip_done()`) then writes `state='level1'`. This is the ONLY correct draft→chain transition.
- ✓ **Tier advances**: `action_payslip_run_level1_done()` (:1010-1025) cascades `line.action_payslip_level1_done()`, writes `level2`, auto-generates batch analytics when param `payroll_analytics_approval.auto_generate` (:1016-1018), returns a GM-notify action. `action_payslip_run_level2_done()` (~:1215) cascades slips, writes `done`, syncs analytics to approved. `action_payslip_run_cancel()` (~:1222) exists. **None of these check groups.**
- ✓ **The hole**: `pb.approval.approve_run` (`pb_approval/models/pb_approval.py:53-64`) browses the run and calls the STAGE method with **no access gate**; `get_approvals` (:36-51) likewise ungated. The only "gates" are UI-visibility computes `_compute_pb_perms` (`pb_payruns/models/hr_payslip_run.py:152-159`: level1 needs `group_payroll_base_manager`, level2 needs `group_payroll_final_approver`).
- ✓ **The mis-wired submit**: `pb_payrun_wizard.submit_for_approval` (`pb_payrun_wizard/models/pb_payrun_wizard.py:295-305`) calls `action_payslip_run_level1_done()` — on a draft run that writes `level2` directly (the method writes unconditionally), skipping HR. It also swallows all exceptions to a bare `ok=False`.
- ✓ **STAGE dict** (`pb_approval/models/pb_approval.py:11-14`): `state → (advance_method, stage_label, role)` — 2 entries. `_run_dict` (:22-34) reads STORED totals `pb_employee_count`/`pb_total_net` (`pb_payruns/models/hr_payslip_run.py:40-52`, computed :78-116 by SQL roll-up on NET/GROSS/DED categories).
- ✓ **Downstream contracts unaffected by inserting level0**: `pb_pay_delivery.get_recent_runs` filters `['|',('state','=','done'),('slip_ids.state','=','done')]` (`pb_pay_delivery/models/pb_pay_delivery.py:107`); analytics fires on reaching level2 (unchanged); pb_payruns kanban group-expand reads the selection dynamically (`hr_payslip_run.py:31-35`) so a new state auto-appears as a column.
- ✓ **Groups already exist** (`pb_hr_payroll_base/security/payroll_base_security_enhanced.xml`): `group_payroll_base_officer` (:77-82), `group_payroll_base_manager` (:84-89, implies officer), `group_payroll_final_approver` (:169-174), `group_payroll_super_admin` (:91-96, implies manager). **No new groups needed.**
- ✓ **Sidebar gate**: "Approvals" item `pb_sidebar/data/pb_sidebar_data.xml:43-50` — manager/final-approver/super-admin only (officer can't see it). Sidebar data is `noupdate` — changing an EXISTING record's groups needs a direct write on live (Phase-F precedent), not just `-u`.
- ✓ **Cockpit**: `ir.actions.client` tag `pb_approval` (`views/pb_approval_action.xml:3-6`); OWL `PbApproval` (`static/src/js/approval.js:7-45` — `load/approve/openRun/stageCls`); template lanes+KPIs (`static/src/xml/approval.xml`, summary :21-38, pending :40-75, recent :78-90); SCSS stage badges amber/indigo/green (`static/src/scss/approval.scss:93-95`). **Pre-design-system styling; zero i18n in the module.**
- ✓ `hr.payslip.run` has **NO `company_id`** (C18.43) and no mail.thread.

---

## 3. Architecture

### `pb_payruns` — state + enforcement (the model layer owns the truth)

1. `state = fields.Selection(selection_add=[('level0', 'Payroll Officer pending'), ('level1',)], ondelete={'level0': 'set draft'})` — the `('level1',)` anchor positions level0 before level1; the legacy base file is untouched.
2. New `action_payslip_run_level0_done()`: first line = tier gate; writes `state='level1'`. **No slip cascade** (slips were confirmed at entry) and no mail.
3. **One tier-gate helper** `_pb_require_tier(state)` → maps `level0→group_payroll_base_officer`, `level1→group_payroll_base_manager`, `level2→group_payroll_final_approver`, super-admin passes all; raises `AccessError` with a friendly role-named message. **Override** `action_payslip_run_level1_done` / `action_payslip_run_level2_done` / `action_payslip_run_cancel` in pb_payruns to call the gate first then `super()` (server-side enforcement lands WITHOUT touching om_hr_payroll; C18.17 — the gate is the model's, not the button's). Cancel additionally requires the run be in a pending state and records `pb_reject_note` (new Char) + `pb_reject_uid`/date.
4. Extend `_compute_pb_perms` with `pb_can_approve_officer` (officer-or-above) so native buttons stay honest.

### `pb_payrun_wizard` — submit seam fix
`submit_for_approval`: if `run.state == 'draft'` call `done_payslip_run()` (which Phase L makes land on `level0` — override in pb_payruns writes `level0` instead of `level1` via `super()`-less rewrite of the tiny method, or simpler: override `done_payslip_run` to call super then `write({'state':'level0'})`… **no** — super confirms slips then writes level1; overriding to re-write level0 after super is two writes but zero legacy edits — acceptable and idempotent; document the double-write in a comment). Non-draft states → friendly `{'ok': False, 'msg': 'Already in approval'}`. Surface the real blocked reason (`str(e)`) instead of a silent `ok=False`.

### `pb_approval` — cockpit + RPC hardening
1. `STAGE` gains `'level0': ('action_payslip_run_level0_done', 'Officer review', 'Payroll Officer')`; relabel level2's cockpit strings to `'Finance approval' / 'Finance / GM'` (state KEY untouched). All three labels become `_()` translatable.
2. **First-line access gate** `_require_access()` on `get_approvals` AND `approve_run` AND the new `reject_run(run_id, note)`: member of officer|manager|final-approver|super-admin else `AccessError` (C18.17 rail — same pattern as `pb_pay_delivery._check_pay_access`).
3. `approve_run`: after the facade gate, the per-tier gate raises inside the model — return `{'ok': False, 'msg': <the model's own message>}` (no more generic "Action blocked"); `get_approvals` pending domain becomes `['level0','level1','level2']`, summary counts `officer/hr/fin`, and each run dict gains `mine: bool` (current user holds that tier's group) so the UI can highlight actionable cards.
4. `reject_run` → `action_payslip_run_cancel` with the note (gated same tier as approve).
5. **vi.po** for every user-facing string — every entry MUST carry its `#. module:` comment (translate.py crash otherwise — Phase-D residual).

### `pb_sidebar` data
Add `group_payroll_base_officer` to the Approvals item's groups. Deploy note: the record is `noupdate` on live — set it via an odoo-shell write in the deploy step (Phase-F precedent), keep the XML as the source of truth for fresh installs.

---

## 4. WOW-UX specification (C18.42 — touched surface gets upgraded)

1. **Pipeline board**: three lanes **Officer review → HR review → Finance approval** (pbim tokens, white+rail hero strip with pending-count KPIs per tier + total NET at stake). Cards: run name, period, employee count, NET headline, a **3-dot chain stepper** (filled = passed tiers), and Approve / Reject actions **only on cards where `mine`** — other lanes render read-only with a "waits on <role>" chip. Recently-approved rail keeps the last 6 with green Done badges.
2. **Reject** = popover with required reason; rejected runs show the reason on the card in the Recently rail (state `cancel`).
3. Lucide icons only (reuse pb_sidebar ICONS / a `pba_icons.js` local set per C18.53 — **new asset file goes in the manifest list + full service restart**), no gradients/emoji, button hierarchy per the locked palette. Empty state: "Nothing awaiting approval."
4. Toasts quote the server's real message on any refusal (never a silent fail).
5. Chrome-MCP validation: board as super-admin (all three lanes actionable), as a crafted officer-only test user (level0 card actionable, level1/2 read-only), reject flow, empty state, 390px responsive.

---

## 5. Safety rails

1. **Tier gates are model-side** (`_pb_require_tier` first line of every advance/cancel override) — the cockpit, native buttons, and any RPC all hit the same wall (C18.17). The facade gate is defense-in-depth, not the guard.
2. **State KEYS are frozen contracts** — `done` stays the downstream approval signal (pb_pay_delivery/analytics verified above); only `level0` is added.
3. **No new mail** (C18.47/48). The existing GM notify stays byte-identical.
4. **Submit is idempotent and honest**: draft-only entry, real error surfaced, no exception swallowing.
5. Demo-pristine: any run advanced during validation is a demo-scheme run or reverted; NEVER click through tiers on live client-visible runs (C18.48 spirit); tests use TransactionCase fixtures.
6. `hr.payslip.run` has no company_id (C18.43) — don't add company filters to `get_approvals`.

---

## 6. Test cases (server, `pb_payruns` + `pb_approval` test dirs)

1. selection order: `level0` sits between `draft` and `level1`.
2. Submit from draft → slips confirmed, run in `level0` (not `level1`, not `level2` — the regression that motivated the fix).
3. Officer advances level0→level1; officer CANNOT advance level1 (AccessError) nor level2.
4. HR manager advances level1→level2; final approver advances level2→done; analytics param path still fires on level2 (mock/param check).
5. A user in NONE of the tier groups: `get_approvals` raises AccessError; `approve_run` raises; direct `action_payslip_run_level1_done()` call raises (the model-side gate — the money assertion of this phase).
6. Super-admin passes every tier.
7. Reject from each pending tier → `cancel` + note stored + `reject_run` gated.
8. `approve_run` on a done/cancel run → `{'ok': False}` friendly.
9. Downstream contract: a `done` run still appears in `pb_pay_delivery.get_recent_runs` (import-guarded if module absent in test env).
10. `submit_for_approval` on a non-draft run → friendly refusal, state unchanged.
11. vi.po loads (module upgrade with vi_VN active — the translate.py `#. module:` guard).
12. `mine` flag correct per tier user in `get_approvals` payload.

**Chrome-MCP:** §4.5 list (three-persona board, reject, empty, 390px) with screenshots.

---

## 7. Deploy & verify (Payobook19v2 — ritual per memory `payobook-deploy`)

`-u pb_payruns,pb_approval,pb_payrun_wizard --test-tags /pb_payruns,/pb_approval` (C18.40 scoping; C18.54 background-run + PID-kill pattern; `--uid=odoo`). Manifest asset changes → full service restart + `/web/assets/%` clear (C18.53). Shell-write the sidebar item's officer group (noupdate). Verify: versions registered; an existing live `done` run still lists in Pay & Deliver; cockpit loads for admin; NO live run advanced.

---

## 8. Report back

1. Tests 1–12 output + 4 screenshots (three personas, reject, empty state — 390px included).
2. Confirm the level2 GM-notify path untouched (diff shows no mail changes) and zero new mail.mail rows from the deploy window.
3. The exact live state of the previously mis-wired seam: how many historical runs sit in `level2`/`done` having SKIPPED level1 (SQL count via the wizard's own log or state history if any) — report only, no data surgery.
4. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_L_APPROVAL_TIER.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.17/40/47/48/53/54), then implement Phase L exactly as specified: insert the Officer tier via `selection_add` in pb_payruns (om_hr_payroll untouched), enforce every tier with model-side `_pb_require_tier` gates (button visibility is never the guard), fix `submit_for_approval` to enter the chain at level0 via `done_payslip_run`, uplift the Approvals cockpit to the pbim 3-lane pipeline with `mine` highlighting and reject-with-reason, and add vi.po. NO new mail sends. Tests §6, deploy §7, report §8.
