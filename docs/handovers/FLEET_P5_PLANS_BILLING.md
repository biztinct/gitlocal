# FLEET P5 — Plans, trial, suspend, usage and invoices

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST, incl. ledger + owner rulings 1–2).
Stands on P2A (`pb_tenancy`, `push_tenancy`, banners), P3 (`pb.alert`, `_send_alert_mail`), P4
(`pb.feature`, `pb.tenant.feature.source = 'plan'`). Gap 7 from `docs/SAAS_RELEASE_STRATEGY.html`.

## Owner rulings this phase implements (2026-09-03)

- Invoices first, card later: the platform raises an invoice each month per customer; the owner
  marks it paid on bank transfer. Overdue → reminders → suspension, and **auto-suspend is a platform
  switch, default OFF**. Leave a clean seam for a payment provider later; wire none.
- A plan can use **any of three price structures**: per active employee / month; per payslip
  produced / month; flat price per company by employee band (tiers). The meter therefore records
  BOTH counts every month for every customer regardless of plan.

## What this phase makes true (plain words)

1. Every customer has a **plan** (name, price structure, price, employee limit, included
   features, currency) and a **state** that now includes `trial`, `suspended` and
   `pending_deletion`, each with the dates that matter (trial ends, suspended since, delete after).
2. Once a month the platform **measures** each customer (active employees on the last day,
   payslips produced in the month), keeps the history, and **raises an invoice** from the plan —
   a PDF the owner can email from the cockpit with one click, and mark paid. Overdue invoices get a
   reminder email to the customer's admin at +3 and +10 days; at +14 the cockpit shows "Suspend?"
   (or suspends by itself only if the switch is on).
3. A **suspended customer's users hit a calm locked door** ("Your Payobook access is paused —
   contact your administrator") instead of a login; the data is untouched; **Resume** is one click.
   A **trial** customer sees a quiet countdown bar in the last 7 days. A customer **over the
   employee limit** sees a notice and cannot add staff until the plan changes.
4. The customer's admin sees a **Plan & usage** card in their own Settings: plan name, this
   month's counts against the limit, invoices with PDF download and paid/unpaid state.
5. Hero moment: the cockpit's **Billing** view — a month strip across the top ("September ·
   3 invoices · 12,400,000 ₫ due · 1 overdue"), a customer table with usage sparklines, and the
   "Raise this month" button that previews every invoice before creating any.

## Binding NON-goals

- No card payments, no payment provider, no dunning automation beyond the two reminders + the
  optional auto-suspend. No tax computation beyond a single VAT % field per plan (default 0; VN
  VAT on software services is the owner's decision — mark as OWNER TO CONFIRM in the report).
- No accounting integration: invoices are the platform's own records, not `account.move`.
- No self-serve signup. Trials are created by the owner from the New-tenant wizard ("Start as a
  14-day trial" toggle).
- `pending_deletion` sets a date and shows it; the deletion itself stays the existing offboard
  action (a person presses, typed confirm) — no automatic deletion.

## Verified facts

- Tenant counts: active employees = `SELECT count(*) FROM hr_employee WHERE active` (the health
  probe SQL, `service.py:246`); payslips in a month = `hr_payslip` rows with `date_from` in the
  month and `state` not in cancelled/draft (verify the selection values in
  `om_hr_payroll/models/hr_payslip.py:53`; count `done` + `verify`? Decide: count every payslip
  whose state is not `draft`/`cancel`, say so on the invoice line label "payslips produced").
- Customer identity for the invoice: `pb.company.profile` on the tenant (`pb_settings/models/
  pb_company_profile.py:158`) exposes name, street, phone, email, vat (:97–107) via its facade —
  read through `_tenant_env` (ORM, rail R5) or SQL on `res_company`/`res_partner` (read-only ok).
- PDF precedent: `pb_hr_payroll_formula/report/payslip_themed.xml` (an `ir.actions.report` +
  QWeb template, Odoo 19 explicit record form — never the `<report>` shortcut, see the deploy
  memory). Reuse its page structure/tokens for the invoice.
- Locked door seam: Odoo 19 `ir.http._authenticate` (`odoo/addons/base/models/ir_http.py:271`)
  / `_pre_dispatch` (:298); web `_pre_dispatch` (`addons/web/models/ir_http.py:57`). The
  recovery account (`platform.recovery@payobook.com`, `base.group_system`) must still get in
  when suspended (P6 uses it).
- Employee creation on a tenant goes through the ORM (`hr.employee.create`) from every cockpit
  and wizard; an override in `pb_tenancy` is enough.
- Currency: abm company currency is VND (provisioning sets it from country). Plans carry their
  own currency; an invoice's currency = the plan's.
- Mail: P3's `_send_alert_mail` seam (explicit `email_from`) — reuse for customer-facing mail
  with a separate template set (invoice, reminder, trial ending, suspended, resumed).

## Architecture

### Apex models (`pb_tenants/models/plan.py`, `billing.py`)

- `pb.plan`: `name`, `code`, `pricing` Selection (`per_employee` / `per_payslip` / `flat_tier`),
  `price` (Float — unit price for the first two), `tier_ids` (One2many `pb.plan.tier`: `up_to`
  employees, `price`), `currency_id`, `employee_limit` (Integer, 0 = unlimited), `vat_pct`
  (Float, default 0), `feature_ids` (M2m `pb.feature` — included features), `trial_days`
  (default 14), `active`, `blurb`. Seed three examples (Starter / Growth / Enterprise) with
  OWNER TO CONFIRM prices in VND; they are data, editable.
- `pb.tenant` gains: `plan_id`, `state` adds `trial`, `suspended`, `pending_deletion`
  (keep the existing five), `trial_ends`, `suspended_at`, `suspend_reason`, `delete_after`,
  `billing_email` (defaults to admin_email), `usage_ids`, `invoice_ids`.
- `pb.tenant.usage`: `tenant_id`, `period` (Date = first of month), `employees` (last-day count),
  `payslips` (count in month), `measured_at`, `sample` JSON (daily employee counts if you also
  sample daily — optional; the month-end number is what bills).
- `pb.tenant.invoice`: `tenant_id`, `number` (`PB-2026-09-0001`, sequence), `period`, `plan_id`
  (snapshot), `line_ids` (`pb.tenant.invoice.line`: label, qty, unit_price, amount),
  `subtotal`, `vat_pct`, `vat_amount`, `total`, `currency_id`, `state` (`draft`/`sent`/`paid`/
  `overdue`/`void`), `issued_at`, `due_date` (+14 d), `sent_at`, `paid_at`, `paid_note`,
  `reminder_count`, `last_reminder_at`, `pdf` (Binary, generated at issue). ACL `base.group_system`.
- **Pure rules** (`billing_rules.py`, T1–T6): `price_for(plan, employees, payslips) -> lines`
  (all three structures; tiers pick the first `up_to >= employees`, last tier open-ended);
  `invoice_totals(lines, vat_pct)`; `next_state(invoice, today)` (draft→sent on send; sent→overdue
  after due; overdue reminders at +3/+10; suspend candidate at +14); `trial_phase(trial_ends,
  today)` → `ok`/`ending` (≤ 7 d)/`ended`; `seat_verdict(limit, count)` → ok/near (≥ 90 %)/full;
  `state_transition(from, to)` allowed pairs (trial→live on "convert", live→suspended, suspended→
  live, live|suspended→pending_deletion, pending_deletion→live "cancel deletion").

### Meter and invoicing (crons, rail R1: reads only on tenants)

- `_cron_meter` daily 23:50 (master tz): for live/trial/suspended tenants read both counts (SQL,
  read-only) into today's sample; on the last day of the month (or first run of a new month) write
  the `pb.tenant.usage` row for the closed month.
- `billing_preview(period)` (dry) and `billing_raise(period)` (person presses — creates DRAFT
  invoices with PDF, one per customer with a plan; skips trial customers with a note; refuses if
  the month is not closed unless `early=True` with a warning). `invoice_send(id)` emails the PDF
  to `billing_email` (state `sent`), `invoice_mark_paid(id, note)`, `invoice_void(id, reason)`.
- `_cron_billing` daily 08:30: overdue transitions, reminders (+3, +10; email to the customer's
  billing email; alert `invoice_overdue` warning via P3), suspend candidates → `alert`
  `suspend_candidate` (critical); if param `pb_tenants.auto_suspend` is on (default OFF) →
  `tenant_suspend(reason='unpaid')`.
- Trial: `_cron_billing` also pushes the trial countdown to the tenant (`pb_tenancy.trial_ends`)
  and emails "trial ends in 7 days / tomorrow / ended" to the admin; at `ended` + grace 3 d →
  suspend candidate alert (auto only with the switch).

### State actions (apex)

- `tenant_suspend(id, reason)` → state `suspended`, `push_tenancy(db, {'pb_tenancy.access':
  'suspended', 'pb_tenancy.access_text': …})`; `tenant_resume(id)` → back to `live` (or `trial`),
  push `access: open`; `tenant_convert(id)` trial → live; `tenant_schedule_deletion(id, days=30)` →
  `pending_deletion` + `delete_after` + a final-backup now; `tenant_cancel_deletion`. Typed-slug
  confirms on suspend and schedule-deletion. Every action logs a `provision_log` line.
- Provisioning wizard: plan picker (required) + "Start as a 14-day trial" toggle; `_step_configure`
  pushes plan/limit/features (P4 `source='plan'` rows written from `plan.feature_ids` — a plan's
  included features become the customer's `plan` rows; manual rows override).

### Tenant side (`pb_tenancy`)

- `state()` adds `access` (`open`/`suspended`), `access_text`, `trial_ends`, `seat_limit`,
  `seat_count` (cheap SQL count, cached 5 min), `plan_name`.
- **Locked door:** `ir.http._pre_dispatch` override: when `access == 'suspended'` and the request
  is authenticated as anyone except the recovery account (login param
  `pb_tenants.break_glass_login` mirrored to the tenant as `pb_tenancy.recovery_login`) or a
  user with `base.group_system`, redirect to `/pb_tenancy/paused` (a public, brand-clean page:
  title, `access_text`, "contact your administrator", no login form). `/web/login` itself keeps
  working (so the recovery account can log in) but a suspended ordinary user lands on the page
  right after login. Static assets and `/pb_tenancy/*` are exempt. Test it does not loop.
- **Seat limit:** `hr.employee.create` override → when `seat_verdict == 'full'` raise a
  `UserError` in plain words ("Your plan allows 50 employees and you already have 50. Ask your
  administrator to change the plan."). `near` → the banner (P2A `notice` kind `info`, local, not
  pushed — the service composes it client-side from `state()`).
- **Trial bar:** last 7 days: amber bar "Your trial ends in 3 days" (from `state()`), dismissable
  daily.
- **Settings card "Plan & usage"** under "About Payobook" (P2A category): plan name/blurb, this
  month's employees vs limit (ring), payslips this month, invoice list (number, period, total,
  state, PDF download via a tenant-side route that proxies the PDF bytes pushed with the invoice —
  push the PDF into the tenant as an attachment on send, so the customer never needs the apex).

### Cockpit (apex)

- **Billing** view (fleet head "Billing" button with due count): month strip; table (customer,
  plan, employees / limit, payslips, this month's amount, invoice state, actions: Preview, Send,
  Mark paid, Void); "Raise September" → preview dialog listing every invoice with its lines and
  total, then Create; usage sparklines (12 months); Plans tab (the catalogue as cards: pricing
  structure segmented control, tiers editor as rows, features multi-select chips, trial days,
  VAT); Settings: auto-suspend switch (with a red explanation), reminder days, due days,
  invoice number prefix, "from" name/email, bank details block printed on the invoice (OWNER TO
  CONFIRM values; blank = a placeholder line on the PDF).
- Tenant detail → **Plan** tab: plan picker, state actions (Convert / Suspend / Resume / Schedule
  deletion / Cancel deletion) with typed confirms, trial dates, the usage/invoice history for
  this customer. Fleet cards: state badges for trial (info, with days left), suspended (rose),
  pending deletion (muted, "deletes after 3 Oct").

### Invoice PDF

QWeb report `pb_tenants.report_tenant_invoice`: Payobook header (brand tokens, no gradients),
"Invoice PB-2026-09-0001", billed-to block (from the tenant's company profile), period, lines,
subtotal / VAT / total in the plan's currency with proper thousand separators, due date, bank
details, footer sentence. Both English and Vietnamese labels if the tenant's company language is
vi_VN (verify how `pb_learn` loaded vi_VN on tenants; keep to a small label map if `.po` is heavy).

### Tests

- **T1** `price_for` all three structures incl. tier edges and zero counts; **T2**
  `invoice_totals` rounding (VND has 0 decimals — use the currency's rounding); **T3** `next_state`
  timeline; **T4** `trial_phase`, `seat_verdict`; **T5** `state_transition` matrix;
  **T6** invoice number sequence per year; **T7** model: `billing_raise` creates drafts with
  PDFs (report renders in test), skips trials, refuses open month; `invoice_mark_paid`;
  `_cron_billing` reminders send once per step (captured sender), auto-suspend only with the
  switch; **T8** tenant-side: `hr.employee.create` refused at the limit, allowed below;
  `_pre_dispatch` redirect for a normal user, pass for the recovery login, no loop on the paused
  page (HttpCase); **T9** existing.

### Live validation

- **L1** Deploy master (`pb_tenants`), template + abm (`pb_tenancy`) via Bring in step
  (rehearse on staging). Seed plans; set abm's plan (OWNER TO CONFIRM which — pick Growth and say
  so); asset ritual everywhere.
- **L2** Meter runs for abm (numbers reported); raise August or September early with the warning;
  preview then create; send the invoice to a test address (set `billing_email` to the owner's
  address for the test and restore); PDF attached, rendered correctly (screenshot); mark paid.
- **L3** Suspend abm on **abm-staging only** (never the live abm without the owner): restore
  staging, suspend it via the facade with the staging name, open it in Chrome as the admin →
  paused page; recovery login still works; resume → normal. Drop staging.
- **L4** Seat limit on staging: set limit = current count → adding an employee refused with the
  sentence; near-limit banner shown. Restore.
- **L5** Trial: create a trial tenant? NO new live tenant (capacity + cost) — set `trial_ends` on
  staging and verify the bar + emails to the test address. Customer "Plan & usage" card on abm
  (live) shows plan + this month + the invoice with PDF download.
- **L6** Chrome-MCP screenshots: Billing view, preview dialog, PDF, Plans tab, Plan tab, paused
  page, seat refusal, trial bar, Plan & usage card. To `docs/handovers/fleet_p5_shots/`.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the Billing month
strip + preview-before-create (Stripe Billing clarity). Zero dead-ends (every refusal names its
next step; the paused page is calm and complete). Plain language: "plan", "employees", "payslips
produced", "invoice", "paused"; never "entitlement", "meter", "dunning". Numbers with thousands
separators and currency symbol. Motion with purpose. No "Odoo" — including the PDF and emails.

## Deploy + verify — as before. Manifests: `pb_tenants` → 19.0.2.0.0, `pb_tenancy` → 19.0.1.2.0.

## Report back — standard list, plus: the seeded plans (prices flagged OWNER TO CONFIRM), the
VAT/bank-details placeholders, the invoice PDF, the exact payslip-state filter used, and the
auto-suspend switch's default and location.
