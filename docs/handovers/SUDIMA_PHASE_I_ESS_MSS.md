# SUDIMA Phase I — ESS & MSS (Self-Service + Manager Cockpit)

**Scope item:** #18 ESS/MSS (*Partial*): ESS today = read-only payslip portal; missing = profile self-edit, tax-sheet view, cert upload, and most of MSS (manager approval queues, team metrics).
**Modules:** NEW **`pb_team`** (MSS backend cockpit for managers) + NEW **`pb_me_portal`** (ESS extensions on the existing `/my` portal).
**Ledger:** C1, C2, C18 binding (esp. C18.24/31 — self-edit NEVER writes master directly; C18.26 company-dependent `employee_id`; C18.32 PII scoping; C18.40).
**Prerequisites:** Phase H shipped (`pb_employee_vault` is the cert-upload target + timeline source). Phases C/D/G chains are the queue content (soft-hooked — the cockpit degrades gracefully if one is absent).

---

## 1. Scope

1. **MSS — "My Team" cockpit** (backend, managers are internal users): one queue for everything awaiting ME — OT requests, business trips (manager tier), attendance corrections, leaves — with one-click approve/refuse routed through each model's EXISTING actions; plus team metrics (week compliance, OT vs ceilings, upcoming leaves, headcount).
2. **ESS — portal extensions**: profile view + **change-request** flow (never direct master writes), personal document upload into the Phase-H vault, tax sheet (PIT summary per payslip), **and a WOW re-skin of the ENTIRE employee portal surface including the existing stock `/my/payslips` pages** — the current pages are stock Odoo portal lists, i.e. legacy, and the binding F–J rule upgrades every legacy surface a phase builds on.
3. Demo enablement: a persistent demo manager login + two portal-linked demo employees (generator-owned).

### Binding non-goals
- **NO native mobile app** (explicit gap-analysis deferral).
- **NO new approval engine** — MSS *consumes* existing chains/actions; it never writes `state` (C18.24 — the mixin token would refuse anyway).
- **NO delegation/vacation rules for approvers** (future).
- **NO ESS edit of bank fields** — bank changes go through the Phase-D OCR chain exclusively (link to it from the portal instead).
- **NO chat/notifications platform** — activities/emails that already fire stay as-is.

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Portal precedent**: `om_hr_payroll/controllers/portal.py` — `/my/payslips` (`auth="user"`, :44), detail with access_token (`auth="public"`, :102); employee resolved `hr.employee.search([('user_id','=',request.env.user.id)])` (:30-35); integrates `CustomerPortal._prepare_home_portal_values`. **C18.26 warning**: `user.employee_id` is company-dependent — resolve via explicit search like :30-35, never `env.user.employee_id`.
- ✓ **No `base.group_portal` usage in the stack** — demo portal users are INTERNAL (`pb_demo_portal/controllers/main.py:235-290` assigns base.group_user etc.). Decision locked (§3): ESS targets **internal** users (demo world reality); the routes themselves work for portal-group users too if a client later wants that — don't block it, don't build for it.
- ✓ **Queue sources** (states + manager linkage all verified):
  - `hr.overtime.request` — states draft/submitted/approved/refused (`pb_hr_workforce/models/overtime_request.py:49-54`), `manager_id` related `employee_id.parent_id` (:20-22), approve action `action_approve`/`approve_requests` bulk (`attendance_weekentry.py:573-581`).
  - `pb.business.trip` — chain states, manager tier = `submitted→manager_approved` where approver IS parent_id's user (`pb_business_trip/models/pb_business_trip.py:94-99,168-196`); advance via its existing action methods only.
  - `hr.attendance.correction` (Phase G) — `submitted→approved`, manager-or-officer.
  - `hr.leave` — hr_holidays IS in the stack (om_hr_payroll dep `__manifest__.py:17`); core states confirm/validate1/validate/refuse; approve via core `action_approve`.
  - `pb.bank.change.request` is NOT a manager queue (HR/finance tiers only) — exclude.
- ✓ **Team = `parent_id` hierarchy** (used by trips :35-36, OT :20-22, People payloads `pb_people.py:111`).
- ✓ **Metrics seams**: OT ceilings `get_ot_ceilings(employee_ids, ref_date)` → mtd/ytd/caps (`attendance_weekentry.py:325-389`); shift compliance statuses (`shift_planning.py:80-101`); Phase-G exception feed (`pb.attendance.exception.engine.get_exceptions`).
- ✓ **Tax sheet source**: payslip lines by code — PIT-relevant codes queryable per slip via `line_ids` (NET precedent `pb_payrun_wizard.py:267`); the VN PIT line codes exist in the formula configs (report-back: list the exact codes you surface — TASSESS/PIT etc. — from the live demo config, don't hardcode; drive by a config param listing codes).
- ✓ **Vault upload target**: `pb.employee.document` + categories (Phase H); C18.25 attachment ordering; own-only record rule to ADD for ESS create (Phase H deliberately left employee-create off).
- ✓ **Cockpit + PWA precedents**: bank cockpit pattern (`pb_bank_ocr.js:24-60`); driver app route gating by group (`driver_app.py:19-87`). Demo-user creation flow with group grants: `pb_demo_portal/controllers/main.py:235-290` (passwordless until demo — C18.14).
- ✓ Versions: om_hr_payroll 19.0.1.0.0, pb_demo_portal 19.0.1.0.0.

---

## 3. Architecture

### `pb_team` (MSS — depends: `hr`, `pb_hr_workforce`, `pb_sidebar`, `pb_import_kit`; soft-hooks: `pb_business_trip`, `pb_attendance_flow`, `hr_holidays`)

- **RPC facade `pb.team`** (AbstractModel): `_my_team()` = `hr.employee.search([('parent_id.user_id','=',uid)])` (+ recursive toggle via `child_of` for skip-level, default direct-only); access gate: user must HAVE a team (else friendly empty state) or be HR.
- `get_team_data()` → `{queues, metrics, roster}`:
  - **queues**: per source model (existence-checked): OT `[('state','=','submitted'),('employee_id','in',team)]`; trips `[('state','=','submitted'),…]` (the tier this user can act on — reuse each record's `can_*` computes rather than re-deriving); corrections submitted; leaves confirm-state. Each item: record ref, employee card, summary line, age chip.
  - **metrics**: this-week compliance mix (from shift statuses), team OT mtd/ytd vs caps (`get_ot_ceilings`), open exceptions count (Phase-G feed, soft), upcoming approved leaves (7d), headcount.
- `act(model, res_id, action, note)` → whitelisted map per model to the EXISTING methods (`action_approve`, `_advance_state` wrappers like `action_hr_approve` equivalents, `action_refuse_chain(note)`, leave `action_approve/action_refuse`) — **the facade never writes state fields**; it calls the model's own gated actions as the clicking user (no sudo — C18.17 one-permission-world: if the user lacks the tier, the model refuses and the cockpit surfaces that message).
- Cockpit tag `pb_team`, sidebar item "My Team" (section Workforce, icon `users`), visible to all internal users (empty-state if no team).

### `pb_me_portal` (ESS — depends: `om_hr_payroll`, `pb_employee_vault`, `biz_approval_chain`, `portal`)

- **`pb.profile.change.request`** (chain mixin — clone the bank-request shape minus OCR): fields `employee_id`, requested changes as explicit columns (`x_phone`, `x_private_email`, `x_address`, `x_emergency_contact`, `x_emergency_phone`) + `cur_*` snapshot (sentinel-guarded `_SYS_FIELDS` — C18.31), states `draft→hr_review→approved|refused`, transitions HR-gated; `_apply_to_master()` single writer with audit-token context so Phase-H `biz_audit_trail` logs the master change with true actor. **The editable field set is a config param whitelist** (`pb_me_portal.editable_fields`) — adding a field is config, but only within the shipped column set.
- **Portal routes** (`auth='user'`, employee resolved per :30-35):
  - `/my/profile` — read card + "Request change" form → creates the request; shows pending/history with the stepper JSON rendered read-only.
  - `/my/documents` — list OWN vault docs + upload (categories flagged `ess_uploadable` on the Phase-H category model — add that Bool here via inherit); C18.25 ordering; new record rule: employee may CREATE documents for self only, may never set `verified*` (already sentinel-guarded).
  - `/my/taxsheet` — per-payslip PIT summary table: lines whose code ∈ config param `pb_me_portal.tax_codes` (resolve actual codes from the live formula config at implementation; report them) + YTD totals. Read-only, own slips only (reuse the :30-35 domain).
  - `/my/payslips` untouched.
  - Portal home cards via `_prepare_home_portal_values` inherit (counts: documents, pending requests).
- **Demo enablement** (generator-owned, Phase-E lesson): extend `pb_demo` — `ensure_ess_demo_users()`: one manager login (linked to an existing demo manager with ~8 reports) + two employee logins (one = a demo minor for the story), all passwordless (C18.14 — password set at demo time), groups: internal user only (+ demo group). Report logins in §8.

---

## 4. WOW-UX specification (exceptional, out-of-world — binding F–J rule: legacy surfaces get upgraded, never left stock)

1. **My Team cockpit**: hero strip (team size, pending count with pulse, compliance donut, OT budget bar) · unified queue with source-colored left borders (OT red per grid legend, trips violet, corrections cyan, leaves green), employee avatars, one-click ✓/✗ with note popover on refuse, optimistic row removal · roster rail with per-member week gauge + exception badges. Designed empty state ("Your team is all caught up") — Chrome-MCP validate it.
2. **Approve interactions**: server message on refusal-by-model surfaces as a toast quoting the model's own error (e.g. young-worker OT block) — never a silent failure.
3. **ESS portal = a full WOW re-skin, not an extension.** The stock `/my/payslips` list and detail pages are LEGACY and get redesigned in this phase into a branded employee hub: a "My Payobook" landing (`/my` cards redesigned — payslips, profile, documents, tax), payslip cards with period + NET headline and a themed-PDF download tile, the detail page matching the themed-payslip design language. New pages (profile, documents, tax sheet) are born WOW: profile shows current → proposed diff preview before submit with the approval stepper; tax sheet = statutory-style table (Phase-E band-table precedent) with YTD summary tiles. Mobile-responsive (this is the phone surface until a native app is ever approved) — validate at 390px width in Chrome MCP.
4. Design-system discipline: pbim tokens on the portal too (scoped bundle — do not leak backend assets wholesale into the portal; a lean `pb_me_portal` frontend bundle carries tokens + components), white+rail hero, Lucide only, no gradients/emoji, button hierarchy per the locked palette.

---

## 5. Safety rails

1. **MSS never writes state** — the facade whitelist calls model actions as the real user; a tier the user lacks refuses at the model (tested).
2. **ESS never writes master** — profile changes only via the chain request's `_apply_to_master` (sentinel context, audited by Phase-H trail); the editable-field whitelist is server-side.
3. **PII**: every portal route re-resolves the employee from the session user (:30-35 pattern); no route accepts an employee_id parameter for own-data pages; documents create = own-only rule; tax sheet own slips only.
4. **Team scoping**: queue domains are team-bounded server-side; a crafted `act()` call on a non-team record still hits the model's own gates (defense in depth — and the facade rejects non-whitelisted models/actions).
5. **C18.26**: employee resolution by explicit search everywhere.
6. Demo users passwordless until demo (C18.14).

---

## 6. Test cases

**Server:**
1. `_my_team` returns direct reports; a user with no team gets the empty-state payload, not an error.
2. Queues: seeded submitted OT + trip + correction + leave for team members appear; a NON-team member's submitted OT does not.
3. `act` whitelist: approving team OT as manager succeeds via the model action; `act('res.users', …)` or a non-whitelisted action string raises; approving a trip tier the user lacks surfaces the model's refusal message (not a crash, not a state change).
4. MSS writes no state directly: grep-level test — `pb.team.act` on a chain model goes through `_advance_state` path (step log row exists with the manager as actor).
5. Profile change: employee submits phone change → HR approves → `hr.employee` updated, `biz.audit.entry` row exists with the true actor, `cur_*`/sys fields client-write raises (C18.31 regression).
6. Whitelist: a request carrying a non-whitelisted field (crafted create) is stripped/refused.
7. ESS documents: employee uploads own cert (C18.25 order asserted), cannot upload for a colleague, cannot set verified; HR sees it in the Phase-H drawer.
8. Tax sheet: config-param codes render with correct amounts for own slips; another employee's slip id in the URL → 404/redirect (access_token discipline like :102).
9. Portal home counters correct.
10. Adults/regression: none of the new rules break the existing `/my/payslips` flow (its tests still green).

**Chrome MCP:**
11. Manager demo login: My Team cockpit, approve an OT from the queue, refusal toast on a young-worker OT (the E-gate message surfacing — screenshot); empty-state after clearing the queue.
12. Employee demo login: profile change flow end-to-end + stepper (screenshot).
13. Tax sheet + document upload from the portal (screenshot).
14. The re-skinned `/my` hub and payslip pages — desktop AND 390px mobile emulation (screenshots of both); confirm no stock-portal styling remains on any /my page an employee reaches.

---

## 7. Deploy & verify

Ritual (`--uid=odoo`). `-i pb_team,pb_me_portal -u pb_demo,pb_employee_vault --test-tags /pb_team,/pb_me_portal` (C18.40). Generator run for the demo logins; verify §6.11-13 with those logins on live; demo world stays pristine (approved test records cleaned or generator-owned).

---

## 8. Report back

1. Tests 1–13 + three screenshots.
2. The exact PIT line codes surfaced on the tax sheet (from the live VN formula config) + where you read them.
3. Demo logins created (emails, no passwords — C18.14) and the generator diff.
4. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_I_ESS_MSS.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.17/24/25/26/31/32), then implement Phase I exactly as specified: `pb_team` (My Team cockpit whose act() facade only ever calls the models' own gated actions as the real user) and `pb_me_portal` (profile change-requests through an approval chain with sentinel-guarded snapshots, own-only vault uploads, config-driven tax sheet). Tests §6, deploy §7, report §8. MSS never writes a state field; ESS never writes the employee master — every mutation rides an existing gated action or an approved request.
