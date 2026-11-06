# FLEET P5 — what shipped, what was measured, and what the owner has to decide

Phase spec: `FLEET_P5_PLANS_BILLING.md`. Program + ledger: `FLEET_PROGRAM.md`
(this phase appended **F52–F61**). Screenshots and the real invoice PDF:
`fleet_p5_shots/`.

## Where everything is

| Database | pb_tenants | pb_tenancy | State after this phase |
|---|---|---|---|
| `payobook` (master) | 19.0.2.0.0 | 19.0.1.3.0 | upgraded, assets purged + version bumped, restarted |
| `payobook_template` | — (never) | 19.0.1.3.0 | brought in step; 0 of 58 scheduled jobs active (rail R8) |
| `abm` (live customer) | — (never) | 19.0.1.3.0 | brought in step after a rehearsal on a restore (rail R4) |
| `abm-staging` | — | 19.0.1.3.0 | used for every destructive test, then dropped |

Tests: **517 pass, 0 failed, 0 errors** across `pb_tenants`, `pb_tenancy`,
`pb_hub`, `pb_settings`, `pb_sidebar`, `pb_import_kit` — every module the phase
touches (F49's scope rule). 129 of those are new.

## The three price structures, proved

| Plan (seeded) | Charges | Price — **OWNER TO CONFIRM** | Employee limit | Trial |
|---|---|---|---|---|
| Starter | per employee, per month | 30,000 ₫ each | 50 | 14 days |
| Growth | per payslip produced | 25,000 ₫ each | 500 | 14 days |
| Enterprise | one monthly price by size band | up to 200 → 6,000,000 ₫ · up to 500 → 12,000,000 ₫ · up to 2,000 → 30,000,000 ₫ | none | 30 days |

Every figure above is a placeholder. Tax is 0 % on all three.

## What was done on the live fleet

* AB Mauri put on **Enterprise** and told about it.
* The meter read them: **153 employees, 0 payslips produced** in August and
  September 2026.
* August previewed, then raised: **PB-2026-08-0001, 6,000,000 ₫**, PDF made,
  emailed to `ash@biztinct.com`, marked paid. `billing_email` was set to that
  address for the send and **restored to empty afterwards** (it falls back to
  the administrator's own address).
* The customer's own database now holds the invoice and its PDF, and their
  "Plan & usage" page opens without touching the platform.
* Pausing, the employee limit and the trial countdown were exercised on
  **`abm-staging` only** and the copy was dropped afterwards. The live customer
  was never paused, never limited and never put on a trial.
* No alerts were left open, and `pb_tenants.auto_suspend` was never written —
  it stands at its code default, **off**.

## Owner decisions

1. **Every price above.** They are placeholders.
2. **Tax.** 0 % on all three plans. VAT on software services in Vietnam is a
   decision only the owner can make.
3. **Bank details, company address and tax number are blank.** The invoice
   prints "Bank details have not been set yet — please reply to the email this
   invoice arrived with and we will send them" and the email leaves the block
   out. Filling them in is four boxes on Billing → Settings.
4. **Which plan AB Mauri is really on.** The spec suggested Growth. Growth
   charges per payslip produced and AB Mauri has produced none (all 36 of their
   payslips are drafts), so it would invoice ₫0. Starter's 50-employee limit
   would have locked a live 153-employee customer out of adding staff.
   Enterprise was the only one of the three that could go on them today.
5. **Auto-suspend stays off** unless the owner says otherwise.
